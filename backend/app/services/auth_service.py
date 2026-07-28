from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from modules.access.application.use_cases import LoginUser
from modules.access.domain import AuthenticationFailed
from modules.access.infrastructure.adapters import build_access_adapters


class AuthService:
    def __init__(self, db: Session) -> None:
        self.adapters = build_access_adapters(db)

    def login(self, email: str, password: str) -> str:
        try:
            token = LoginUser(
                self.adapters.access,
                self.adapters.passwords,
                self.adapters.tokens,
                self.adapters.audit,
                self.adapters.transaction,
            ).execute(email, password)
        except AuthenticationFailed as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
        return token.access_token
