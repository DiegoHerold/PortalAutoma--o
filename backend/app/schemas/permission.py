from pydantic import BaseModel


class CategoryPermissionRead(BaseModel):
    id: int | None = None
    category_id: int
    category_name: str | None = None
    can_view: bool
    can_execute: bool
    can_create: bool
    can_edit: bool
    can_delete: bool
    can_approve: bool

    class Config:
        from_attributes = True


class CategoryPermissionUpdate(BaseModel):
    category_id: int
    can_view: bool = False
    can_execute: bool = False
    can_create: bool = False
    can_edit: bool = False
    can_delete: bool = False
    can_approve: bool = False
