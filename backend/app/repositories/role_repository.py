from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.role import Role


class RoleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_all(self) -> list[Role]:
        return list(self.db.scalars(select(Role).order_by(Role.name)).all())

    def get_by_slug(self, slug: str) -> Role | None:
        return self.db.scalar(select(Role).where(Role.slug == slug))

    def get(self, role_id: int) -> Role | None:
        return self.db.get(Role, role_id)

    def create(self, role: Role) -> Role:
        self.db.add(role)
        self.db.commit()
        self.db.refresh(role)
        return role
