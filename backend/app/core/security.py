from modules.access.infrastructure.authentication import JwtTokenIssuer
from modules.access.infrastructure.hashing import PasslibPasswordHasher


_tokens = JwtTokenIssuer()
_passwords = PasslibPasswordHasher()


def create_access_token(subject: str) -> str:
    return _tokens.create_access_token(subject)


def decode_token(token: str) -> dict:
    return _tokens.decode_access_token(token)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _passwords.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return _passwords.hash(password)


def create_package_download_token(bucket: str, object_key: str, expires_seconds: int = 300) -> str:
    return _tokens.create_package_download_token(bucket, object_key, expires_seconds)


def decode_package_download_token(token: str) -> dict:
    return _tokens.decode_package_download_token(token)
