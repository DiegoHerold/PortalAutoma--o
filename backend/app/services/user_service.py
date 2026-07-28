from sqlalchemy.orm import Session

from modules.access.application.use_cases import CreateUser, DeleteUser, ListUsers, UpdateUser, UpdateUserPermissions
from modules.access.infrastructure.adapters import build_access_adapters


class UserService:
    def __init__(self, db: Session) -> None:
        self.adapters = build_access_adapters(db)

    def list_users(self, current_user):
        return ListUsers(self.adapters.access).execute(current_user)

    def create_user(self, current_user, payload):
        return CreateUser(
            self.adapters.access,
            self.adapters.passwords,
            self.adapters.audit,
            self.adapters.transaction,
        ).execute(current_user, payload.model_dump())

    def update_user(self, current_user, user_id: int, payload):
        return UpdateUser(
            self.adapters.access,
            self.adapters.passwords,
            self.adapters.audit,
            self.adapters.transaction,
        ).execute(current_user, user_id, payload.model_dump())

    def update_permissions(self, current_user, user_id: int, payload):
        return UpdateUserPermissions(
            self.adapters.access,
            self.adapters.audit,
            self.adapters.transaction,
        ).execute(current_user, user_id, [item.model_dump() for item in payload.permissions])

    def delete_user(self, current_user, user_id: int) -> None:
        DeleteUser(self.adapters.access, self.adapters.audit, self.adapters.transaction).execute(current_user, user_id)
