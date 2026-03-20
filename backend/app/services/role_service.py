from sqlalchemy.orm import Session

from app.models.role import Role
from app.repositories.role_repository import RoleRepository


class RoleService:
    def __init__(self, db: Session) -> None:
        self.roles = RoleRepository(db)

    def list_roles(self) -> list[Role]:
        return self.roles.list_all()
