import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from modules.catalog.domain.package import (
    build_package,
    find_single_root_dir,
    is_excluded,
    safe_extract_zip,
)

AUTOMATION_YAML = """
schema_version: 1
id: dominio.atualizar
name: Atualizar Domínio Contábil
version: 1.0.0
runtime:
  id: python-desktop
  version: 1
entrypoint:
  type: python-function
  module: atualizar_dominio.main
  callable: run
execution:
  interactive_session: true
  timeout_seconds: 7200
"""


def _make_source_automation(root: Path, *, junk: bool = True) -> Path:
    automation_dir = root / "atualizar-dominio"
    (automation_dir / "src" / "atualizar_dominio").mkdir(parents=True)
    (automation_dir / "automation.yaml").write_text(AUTOMATION_YAML, encoding="utf-8")
    (automation_dir / "src" / "atualizar_dominio" / "__init__.py").write_text("", encoding="utf-8")
    (automation_dir / "src" / "atualizar_dominio" / "main.py").write_text(
        "async def run(context):\n    return {}\n", encoding="utf-8"
    )
    (automation_dir / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (automation_dir / "resources" / "template.docx").parent.mkdir(exist_ok=True)
    (automation_dir / "resources" / "template.docx").write_bytes(b"fake-binary")
    if junk:
        (automation_dir / ".git").mkdir()
        (automation_dir / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        (automation_dir / ".venv").mkdir()
        (automation_dir / ".venv" / "pyvenv.cfg").write_text("", encoding="utf-8")
        (automation_dir / "tests").mkdir()
        (automation_dir / "tests" / "test_main.py").write_text("def test_x(): ...\n", encoding="utf-8")
        (automation_dir / "__pycache__").mkdir()
        (automation_dir / "__pycache__" / "main.cpython-311.pyc").write_bytes(b"junk")
        (automation_dir / ".env").write_text("SECRET=abc\n", encoding="utf-8")
    return automation_dir


def test_build_package_excludes_junk_and_maps_src_to_application(tmp_path: Path):
    source = _make_source_automation(tmp_path)
    output = tmp_path / "out" / "package.zip"

    result = build_package(
        source_root=source,
        output_zip_path=output,
        raw_manifest_yaml=AUTOMATION_YAML,
        package_metadata={
            "source": "manual_upload",
            "package_sha256": "placeholder",
        },
    )

    assert result.zip_path == output
    assert result.application_type == "source"
    assert result.size > 0
    assert len(result.sha256) == 64

    with zipfile.ZipFile(output) as zf:
        names = set(zf.namelist())

    assert "automation.yaml" in names
    assert "application/atualizar_dominio/main.py" in names
    assert "application/atualizar_dominio/__init__.py" in names
    assert "pyproject.toml" in names
    assert "resources/template.docx" in names
    assert "package-metadata.json" in names

    # Junk must never be included.
    assert not any(".git" in n for n in names)
    assert not any(".venv" in n for n in names)
    assert not any("__pycache__" in n for n in names)
    assert not any(n.startswith("tests/") or "/tests/" in n for n in names)
    assert not any(n.endswith(".env") for n in names)
    assert not any(n.endswith(".pyc") for n in names)


def test_build_package_hash_matches_file_content(tmp_path: Path):
    source = _make_source_automation(tmp_path, junk=False)
    output = tmp_path / "package.zip"
    result = build_package(
        source_root=source,
        output_zip_path=output,
        raw_manifest_yaml=AUTOMATION_YAML,
        package_metadata={"source": "manual_upload"},
    )
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    assert digest == result.sha256


def test_build_package_metadata_contents(tmp_path: Path):
    source = _make_source_automation(tmp_path, junk=False)
    output = tmp_path / "package.zip"
    build_package(
        source_root=source,
        output_zip_path=output,
        raw_manifest_yaml=AUTOMATION_YAML,
        package_metadata={
            "source": "github",
            "repository": "biason/biason-automations",
            "branch": "main",
            "path": "automations/dominio/atualizar-dominio",
            "commit_sha": "abc123",
        },
    )
    with zipfile.ZipFile(output) as zf:
        meta = json.loads(zf.read("package-metadata.json"))
    assert meta["source"] == "github"
    assert meta["repository"] == "biason/biason-automations"
    assert meta["commit_sha"] == "abc123"
    assert "created_at" in meta


def test_build_package_already_packaged_shape_passes_through(tmp_path: Path):
    automation_dir = tmp_path / "prepackaged"
    (automation_dir / "application" / "atualizar_dominio").mkdir(parents=True)
    (automation_dir / "automation.yaml").write_text(AUTOMATION_YAML, encoding="utf-8")
    (automation_dir / "application" / "atualizar_dominio" / "main.py").write_text(
        "async def run(context):\n    return {}\n", encoding="utf-8"
    )
    output = tmp_path / "package.zip"
    result = build_package(
        source_root=automation_dir,
        output_zip_path=output,
        raw_manifest_yaml=AUTOMATION_YAML,
        package_metadata={"source": "manual_upload"},
    )
    assert result.application_type == "source"
    with zipfile.ZipFile(output) as zf:
        assert "application/atualizar_dominio/main.py" in zf.namelist()


def test_build_package_missing_manifest_raises(tmp_path: Path):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    with pytest.raises(ValueError, match="automation.yaml"):
        build_package(
            source_root=empty_dir,
            output_zip_path=tmp_path / "out.zip",
            raw_manifest_yaml=AUTOMATION_YAML,
            package_metadata={},
        )


def test_is_excluded():
    assert is_excluded(Path(".git/HEAD"))
    assert is_excluded(Path("tests/test_main.py"))
    assert is_excluded(Path("nested/__pycache__/x.pyc"))
    assert is_excluded(Path(".env"))
    assert is_excluded(Path(".env.production"))
    assert is_excluded(Path("app.log"))
    assert not is_excluded(Path("src/pkg/main.py"))
    assert not is_excluded(Path("resources/template.docx"))


def test_safe_extract_zip_rejects_path_traversal(tmp_path: Path):
    evil_zip = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil_zip, "w") as zf:
        zf.writestr("../../etc/passwd", "pwned")

    destination = tmp_path / "extracted"
    with pytest.raises(ValueError, match="Unsafe ZIP entry path"):
        safe_extract_zip(evil_zip, destination)


def test_safe_extract_zip_accepts_normal_archive(tmp_path: Path):
    good_zip = tmp_path / "good.zip"
    with zipfile.ZipFile(good_zip, "w") as zf:
        zf.writestr("automation.yaml", AUTOMATION_YAML)
        zf.writestr("src/pkg/main.py", "async def run(ctx): return {}")

    destination = tmp_path / "extracted"
    safe_extract_zip(good_zip, destination)
    assert (destination / "automation.yaml").is_file()
    assert (destination / "src" / "pkg" / "main.py").is_file()


def test_find_single_root_dir_unwraps_one_folder(tmp_path: Path):
    (tmp_path / "atualizar-dominio").mkdir()
    (tmp_path / "atualizar-dominio" / "automation.yaml").write_text(AUTOMATION_YAML, encoding="utf-8")
    assert find_single_root_dir(tmp_path) == tmp_path / "atualizar-dominio"


def test_find_single_root_dir_keeps_root_when_files_at_top_level(tmp_path: Path):
    (tmp_path / "automation.yaml").write_text(AUTOMATION_YAML, encoding="utf-8")
    (tmp_path / "src").mkdir()
    assert find_single_root_dir(tmp_path) == tmp_path
