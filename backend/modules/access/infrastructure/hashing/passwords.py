from __future__ import annotations

from passlib.context import CryptContext


class PasslibPasswordHasher:
    def __init__(self) -> None:
        self.context = CryptContext(schemes=["bcrypt_sha256", "bcrypt"], deprecated="auto")

    def hash(self, password: str) -> str:
        return self.context.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        return self.context.verify(password, password_hash)

