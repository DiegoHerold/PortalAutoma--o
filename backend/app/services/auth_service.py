from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, verify_password
from app.repositories.user_repository import UserRepository
from app.services.audit_service import AuditService


class AuthService:
    def __init__(self, db: Session) -> None:
        self.audit = AuditService(db)
        self.users = UserRepository(db)

    def login(self, email: str, password: str) -> str:
        user = self.users.get_by_email(email)
        if not user or not user.is_active or not verify_password(password, user.password_hash):
            self.audit.record("login_failed", actor_email=email, resource_type="user", details="Invalid credentials.")
            self.users.db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )
        self.audit.record("login_succeeded", actor_email=user.email, resource_type="user", resource_id=str(user.id))
        self.users.db.commit()
        return create_access_token(str(user.id))
