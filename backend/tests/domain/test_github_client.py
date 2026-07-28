import hashlib
import hmac

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.config import get_settings
from infrastructure.github.client import GithubAppClient, GithubAppNotConfiguredError, verify_webhook_signature


def _generate_pem_private_key() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return pem.decode("utf-8")


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_client_raises_when_not_configured(monkeypatch):
    monkeypatch.delenv("GITHUB_APP_ID", raising=False)
    monkeypatch.delenv("GITHUB_APP_PRIVATE_KEY", raising=False)
    get_settings.cache_clear()
    with pytest.raises(GithubAppNotConfiguredError):
        GithubAppClient()


def test_app_jwt_is_signed_correctly(monkeypatch):
    private_key_pem = _generate_pem_private_key()
    monkeypatch.setenv("GITHUB_APP_ID", "123456")
    monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY", private_key_pem)
    get_settings.cache_clear()

    client = GithubAppClient()
    token = client._app_jwt()

    public_key = serialization.load_pem_private_key(private_key_pem.encode(), password=None).public_key()
    decoded = jwt.decode(token, public_key, algorithms=["RS256"])
    assert decoded["iss"] == "123456"
    assert decoded["exp"] > decoded["iat"]


def test_install_url_requires_slug(monkeypatch):
    private_key_pem = _generate_pem_private_key()
    monkeypatch.setenv("GITHUB_APP_ID", "123456")
    monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY", private_key_pem)
    monkeypatch.delenv("GITHUB_APP_SLUG", raising=False)
    get_settings.cache_clear()

    client = GithubAppClient()
    with pytest.raises(GithubAppNotConfiguredError):
        client.install_url()


def test_install_url_with_slug(monkeypatch):
    private_key_pem = _generate_pem_private_key()
    monkeypatch.setenv("GITHUB_APP_ID", "123456")
    monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY", private_key_pem)
    monkeypatch.setenv("GITHUB_APP_SLUG", "biason-automations-portal")
    get_settings.cache_clear()

    client = GithubAppClient()
    assert client.install_url() == "https://github.com/apps/biason-automations-portal/installations/new"


def test_verify_webhook_signature_valid():
    body = b'{"zen": "hello"}'
    secret = "s3cr3t"
    signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_webhook_signature(body, signature, secret) is True


def test_verify_webhook_signature_invalid():
    body = b'{"zen": "hello"}'
    assert verify_webhook_signature(body, "sha256=deadbeef", "s3cr3t") is False


def test_verify_webhook_signature_missing_header():
    assert verify_webhook_signature(b"{}", None, "s3cr3t") is False


def test_verify_webhook_signature_tampered_payload():
    body = b'{"zen": "hello"}'
    secret = "s3cr3t"
    signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    tampered_body = b'{"zen": "goodbye"}'
    assert verify_webhook_signature(tampered_body, signature, secret) is False
