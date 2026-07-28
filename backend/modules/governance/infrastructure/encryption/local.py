from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet

from infrastructure.config import get_settings


class LocalFernetSecretCipher:
    key_id = "local:v1"

    def __init__(self) -> None:
        settings = get_settings()
        material = settings.governance_local_encryption_key or settings.secret_key
        key = base64.urlsafe_b64encode(hashlib.sha256(material.encode("utf-8")).digest())
        self._fernet = Fernet(key)

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode("utf-8")).decode("ascii")

    def decrypt(self, value: str) -> str:
        return self._fernet.decrypt(value.encode("ascii")).decode("utf-8")
