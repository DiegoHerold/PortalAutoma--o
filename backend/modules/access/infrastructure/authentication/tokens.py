from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from jose import jwt

from infrastructure.config import get_settings


class JwtTokenIssuer:
    def __init__(self) -> None:
        self.settings = get_settings()

    def create_access_token(self, subject: str) -> str:
        expire = datetime.now(UTC) + timedelta(minutes=self.settings.access_token_expire_minutes)
        return self._encode({"sub": subject, "exp": expire})

    def decode_access_token(self, token: str) -> dict[str, Any]:
        return jwt.decode(token, self.settings.secret_key, algorithms=[self.settings.algorithm])

    def create_package_download_token(self, bucket: str, object_key: str, expires_seconds: int = 300) -> str:
        expire = datetime.now(UTC) + timedelta(seconds=expires_seconds)
        return self._encode({"scope": "package_download", "bucket": bucket, "object_key": object_key, "exp": expire})

    def decode_package_download_token(self, token: str) -> dict[str, Any]:
        payload = self.decode_access_token(token)
        if payload.get("scope") != "package_download":
            raise ValueError("Token invalido para download de pacote.")
        return payload

    def _encode(self, payload: dict[str, Any]) -> str:
        return jwt.encode(payload, self.settings.secret_key, algorithm=self.settings.algorithm)

