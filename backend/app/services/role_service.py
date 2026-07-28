from sqlalchemy.orm import Session

from modules.access.application.use_cases import ListRoles
from modules.access.infrastructure.adapters import build_access_adapters


class RoleService:
    def __init__(self, db: Session) -> None:
        self.adapters = build_access_adapters(db)

    def list_roles(self):
        return ListRoles(self.adapters.access).execute()
