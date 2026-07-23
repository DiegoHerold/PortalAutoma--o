from pathlib import Path

import pytest

from app.core.config import get_settings
from app.core.security import decode_package_download_token
from app.integrations.storage.local_storage import LocalPackageStorage


@pytest.fixture(autouse=True)
def _local_storage_root(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCAL_STORAGE_PATH", str(tmp_path / "packages"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_put_and_exists(tmp_path: Path):
    storage = LocalPackageStorage()
    src = tmp_path / "package.zip"
    src.write_bytes(b"fake-zip-bytes")

    stored = storage.put("automations", "dominio.atualizar/1.0.0/package.zip", src)

    assert stored.bucket == "automations"
    assert stored.size == len(b"fake-zip-bytes")
    assert storage.exists("automations", "dominio.atualizar/1.0.0/package.zip")
    assert storage.open_local_path("automations", "dominio.atualizar/1.0.0/package.zip").read_bytes() == b"fake-zip-bytes"


def test_get_download_url_contains_valid_signed_token(tmp_path: Path):
    storage = LocalPackageStorage()
    src = tmp_path / "package.zip"
    src.write_bytes(b"x")
    storage.put("automations", "k/1.0.0/package.zip", src)

    url = storage.get_download_url("automations", "k/1.0.0/package.zip", expires_in_seconds=60)
    assert "token=" in url
    token = url.split("token=", 1)[1]
    payload = decode_package_download_token(token)
    assert payload["bucket"] == "automations"
    assert payload["object_key"] == "k/1.0.0/package.zip"


def test_delete_removes_object(tmp_path: Path):
    storage = LocalPackageStorage()
    src = tmp_path / "package.zip"
    src.write_bytes(b"x")
    storage.put("b", "k.zip", src)
    assert storage.exists("b", "k.zip")
    storage.delete("b", "k.zip")
    assert not storage.exists("b", "k.zip")
