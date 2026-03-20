from pydantic import BaseModel

from app.schemas.permission import CategoryPermissionRead

class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AuthenticatedUser(BaseModel):
    id: int
    email: str
    name: str
    role: str
    permissions: list[CategoryPermissionRead] = []
