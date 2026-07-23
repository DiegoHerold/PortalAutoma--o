from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.user import User
from app.models.user_category_permission import UserCategoryPermission
from app.repositories.role_repository import RoleRepository
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate
from app.schemas.user import UserPermissionsUpdate
from app.schemas.user import UserUpdate
from app.services.audit_service import AuditService
from app.services.permission_service import PermissionService


class UserService:
    def __init__(self, db: Session) -> None:
        self.audit = AuditService(db)
        self.db = db
        self.permissions = PermissionService(db)
        self.roles = RoleRepository(db)
        self.users = UserRepository(db)

    def list_users(self, current_user: User) -> list[User]:
        self.permissions.ensure_admin_or_manager(current_user)
        return self.users.list_all()

    def create_user(self, current_user: User, payload: UserCreate) -> User:
        self.permissions.ensure_admin_or_manager(current_user)
        if self.roles.get(payload.role_id) is None:
            raise ValueError("Selected role was not found.")
        user = User(
            name=payload.name.strip(),
            email=payload.email.strip(),
            password_hash=get_password_hash(payload.password),
            role_id=payload.role_id,
            is_active=payload.is_active,
        )
        created = self.users.create(user)
        self.audit.record(
            "user_created",
            actor_email=current_user.email,
            resource_type="user",
            resource_id=str(created.id),
            details=created.email,
        )
        self.db.commit()
        return created

    def update_user(self, current_user: User, user_id: int, payload: UserUpdate) -> User:
        self.permissions.ensure_admin_or_manager(current_user)
        user = self.users.get(user_id)
        if user is None:
            raise ValueError("User not found.")
        if self.roles.get(payload.role_id) is None:
            raise ValueError("Selected role was not found.")
        user.name = payload.name.strip()
        user.email = payload.email.strip()
        user.role_id = payload.role_id
        user.is_active = payload.is_active
        if payload.password:
            user.password_hash = get_password_hash(payload.password)
        updated = self.users.update(user)
        self.audit.record(
            "user_updated",
            actor_email=current_user.email,
            resource_type="user",
            resource_id=str(updated.id),
            details=updated.email,
        )
        self.db.commit()
        return updated

    def update_permissions(
        self,
        current_user: User,
        user_id: int,
        payload: UserPermissionsUpdate,
    ) -> User:
        self.permissions.ensure_admin_or_manager(current_user)
        user = self.users.get(user_id)
        if user is None:
            raise ValueError("User not found.")
        for permission_payload in payload.permissions:
            permission = self.users.get_permission(user.id, permission_payload.category_id)
            if permission is None:
                permission = UserCategoryPermission(
                    user_id=user.id,
                    category_id=permission_payload.category_id,
                )
                self.users.create_permission(permission)
            permission.can_view = permission_payload.can_view
            permission.can_execute = permission_payload.can_execute
            permission.can_create = permission_payload.can_create
            permission.can_edit = permission_payload.can_edit
            permission.can_delete = permission_payload.can_delete
            permission.can_approve = permission_payload.can_approve
        self.db.commit()
        updated_user = self.users.get(user.id)
        self.audit.record(
            "user_permissions_updated",
            actor_email=current_user.email,
            resource_type="user",
            resource_id=str(user.id),
            details=user.email,
        )
        self.db.commit()
        if updated_user is None:
            raise ValueError("User not found.")
        return updated_user

    def delete_user(self, current_user: User, user_id: int) -> None:
        self.permissions.ensure_admin_or_manager(current_user)
        user = self.users.get(user_id)
        if user is None:
            raise ValueError("User not found.")
        if user.id == current_user.id:
            raise ValueError("You cannot delete your own user.")
        self.audit.record(
            "user_deleted",
            actor_email=current_user.email,
            resource_type="user",
            resource_id=str(user.id),
            details=user.email,
        )
        if not user.requested_jobs:
            for permission in list(user.category_permissions):
                self.db.delete(permission)
            self.users.delete(user)
            return
        user.is_active = False
        self.users.update(user)
        self.db.commit()
