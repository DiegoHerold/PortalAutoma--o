from pydantic import BaseModel, Field

from app.schemas.permission import CategoryPermissionRead, CategoryPermissionUpdate
from app.schemas.role import RoleRead


class UserCreate(BaseModel):
    name: str = Field(min_length=1)
    email: str = Field(min_length=3)
    password: str = Field(min_length=1)
    role_id: int = Field(gt=0)
    is_active: bool = True


class UserUpdate(BaseModel):
    name: str = Field(min_length=1)
    email: str = Field(min_length=3)
    role_id: int = Field(gt=0)
    is_active: bool = True
    password: str | None = None


class UserRead(BaseModel):
    id: int
    name: str
    email: str
    is_active: bool
    role: RoleRead
    category_permissions: list[CategoryPermissionRead] = []

    class Config:
        from_attributes = True


class UserPermissionsUpdate(BaseModel):
    permissions: list[CategoryPermissionUpdate]
