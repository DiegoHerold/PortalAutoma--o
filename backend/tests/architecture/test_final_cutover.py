from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_backend_app_directory_was_removed() -> None:
    assert not (BACKEND / "app").exists()


def test_official_backend_layers_do_not_import_legacy_app() -> None:
    official_roots = [
        BACKEND / "api",
        BACKEND / "bootstrap",
        BACKEND / "gateway",
        BACKEND / "infrastructure",
        BACKEND / "modules",
        BACKEND / "scripts",
        BACKEND / "workers",
    ]
    violations: list[str] = []
    for root in official_roots:
        for path in sorted(root.rglob("*.py")):
            source = read(path)
            if "from app." in source or "import app." in source:
                violations.append(str(path.relative_to(ROOT)))

    assert violations == []


def test_runtime_entrypoints_use_official_main() -> None:
    dockerfile = read(BACKEND / "Dockerfile")
    compose = read(ROOT / "docker-compose.yml")

    assert "uvicorn main:app" in dockerfile
    assert "uvicorn main:app" in compose
    assert "app.main:app" not in dockerfile
    assert "app.main:app" not in compose
