from datetime import UTC, datetime, timedelta

from jose import jwt
from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt_sha256", "bcrypt"], deprecated="auto")
settings = get_settings()


def create_access_token(subject: str) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_package_download_token(bucket: str, object_key: str, expires_seconds: int = 300) -> str:
    """Short-lived, scope-limited token allowing an Automation Agent to download one package."""
    expire = datetime.now(UTC) + timedelta(seconds=expires_seconds)
    payload = {"scope": "package_download", "bucket": bucket, "object_key": object_key, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_package_download_token(token: str) -> dict:
    payload = decode_token(token)
    if payload.get("scope") != "package_download":
        raise ValueError("Token inválido para download de pacote.")
    return payload
