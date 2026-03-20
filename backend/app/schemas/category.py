from pydantic import BaseModel


class CategoryCreate(BaseModel):
    name: str
    slug: str
    description: str | None = None
    is_active: bool = True


class CategoryUpdate(BaseModel):
    name: str
    slug: str
    description: str | None = None
    is_active: bool = True


class CategoryRead(BaseModel):
    id: int
    name: str
    slug: str
    description: str | None = None
    is_active: bool

    class Config:
        from_attributes = True
