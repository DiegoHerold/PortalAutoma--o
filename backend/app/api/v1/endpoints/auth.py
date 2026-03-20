from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user
from app.schemas.auth import AuthenticatedUser, LoginRequest, TokenResponse
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    token = AuthService(db).login(payload.email, payload.password)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=AuthenticatedUser)
def me(user=Depends(get_current_user)) -> AuthenticatedUser:
    return AuthenticatedUser(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role.slug,
        permissions=user.category_permissions,
    )
