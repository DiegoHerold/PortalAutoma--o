from sqlalchemy.orm import Session

from app.core.permissions import is_admin
from app.models.category import Category
from app.models.user import User
from app.repositories.category_repository import CategoryRepository
from app.schemas.category import CategoryCreate, CategoryUpdate
from app.services.audit_service import AuditService
from app.services.permission_service import PermissionService


class CategoryService:
    def __init__(self, db: Session) -> None:
        self.audit = AuditService(db)
        self.db = db
        self.categories = CategoryRepository(db)
        self.permissions = PermissionService(db)

    def list_categories(self, user: User) -> list[Category]:
        categories = self.categories.list_all()
        if is_admin(user):
            return categories

        allowed_category_ids = {
            permission.category_id for permission in user.category_permissions if permission.can_view
        }
        return [category for category in categories if category.id in allowed_category_ids]

    def create_category(self, user: User, payload: CategoryCreate) -> Category:
        self.permissions.ensure_admin_or_manager(user)
        category = self.categories.create(Category(**payload.model_dump()))
        self.audit.record(
            "category_created",
            actor_email=user.email,
            resource_type="category",
            resource_id=str(category.id),
            details=category.slug,
        )
        self.db.commit()
        return category

    def update_category(self, user: User, category_id: int, payload: CategoryUpdate) -> Category:
        self.permissions.ensure_admin_or_manager(user)
        category = self.categories.get(category_id)
        if category is None:
            raise ValueError("Category not found.")
        for field, value in payload.model_dump().items():
            setattr(category, field, value)
        category = self.categories.update(category)
        self.audit.record(
            "category_updated",
            actor_email=user.email,
            resource_type="category",
            resource_id=str(category.id),
            details=category.slug,
        )
        self.db.commit()
        return category

    def delete_category(self, user: User, category_id: int) -> None:
        self.permissions.ensure_admin_or_manager(user)
        category = self.categories.get(category_id)
        if category is None:
            raise ValueError("Category not found.")
        self.audit.record(
            "category_deleted",
            actor_email=user.email,
            resource_type="category",
            resource_id=str(category.id),
            details=category.slug,
        )
        if category.automations or category.user_permissions:
            category.is_active = False
            self.categories.update(category)
            self.db.commit()
            return
        self.categories.delete(category)
