from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.constants import GlobalRoleSlug
from app.core.security import get_password_hash
from app.models.category import Category
from app.models.role import Role
from app.models.user import User
from app.models.user_category_permission import UserCategoryPermission
from app.models.worker import Worker
from app.repositories.category_repository import CategoryRepository
from app.repositories.role_repository import RoleRepository
from app.repositories.user_repository import UserRepository

DEFAULT_CATEGORIES = (
    ("rh", "RH"),
    ("fiscal", "Fiscal"),
    ("contabil", "Contabil"),
    ("certificados", "Certificados"),
    ("dominio", "Dominio"),
    ("infra", "Infra"),
    ("financeiro", "Financeiro"),
    ("geral", "Geral"),
)


class BootstrapService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.roles = RoleRepository(db)
        self.categories = CategoryRepository(db)
        self.users = UserRepository(db)

    def ensure_defaults(self) -> None:
        self._ensure_roles()
        self._ensure_categories()
        self._ensure_admin()
        self._ensure_admin_permissions()
        self._ensure_default_worker()

    def _ensure_roles(self) -> None:
        default_roles = (
            (GlobalRoleSlug.ADMIN, "Admin", "Full platform access."),
            (GlobalRoleSlug.MANAGER, "Manager", "Operational management with limits."),
            (GlobalRoleSlug.OPERATOR, "Operator", "Execution and operational usage."),
            (GlobalRoleSlug.VIEWER, "Viewer", "Read only access."),
        )
        for slug, name, description in default_roles:
            if self.roles.get_by_slug(slug):
                continue
            self.db.add(Role(name=name, slug=slug, description=description))
        self.db.commit()

    def _ensure_categories(self) -> None:
        for slug, name in DEFAULT_CATEGORIES:
            if self.categories.get_by_slug(slug):
                continue
            self.db.add(Category(name=name, slug=slug, description=f"{name} automations"))
        self.db.commit()

    def _ensure_admin(self) -> None:
        if self.users.get_by_email(self.settings.first_superuser_email):
            return
        admin_role = self.roles.get_by_slug(GlobalRoleSlug.ADMIN)
        if admin_role is None:
            raise RuntimeError("Admin role must exist before creating the default user.")
        self.db.add(
            User(
                name=self.settings.first_superuser_name,
                email=self.settings.first_superuser_email,
                password_hash=get_password_hash(self.settings.first_superuser_password),
                role_id=admin_role.id,
                is_active=True,
            )
        )
        self.db.commit()

    def _ensure_admin_permissions(self) -> None:
        admin = self.users.get_by_email(self.settings.first_superuser_email)
        if admin is None:
            return
        categories = self.categories.list_all()
        for category in categories:
            existing = next(
                (
                    permission
                    for permission in admin.category_permissions
                    if permission.category_id == category.id
                ),
                None,
            )
            if existing:
                continue
            self.db.add(
                UserCategoryPermission(
                    user_id=admin.id,
                    category_id=category.id,
                    can_view=True,
                    can_execute=True,
                    can_create=True,
                    can_edit=True,
                    can_delete=True,
                    can_approve=True,
                )
            )
        self.db.commit()

    def _ensure_default_worker(self) -> None:
        worker = self.db.query(Worker).filter(Worker.hostname == "local-simulated-worker").first()
        if worker:
            return
        self.db.add(
            Worker(
                name="Local Simulated Worker",
                hostname="local-simulated-worker",
                ip_address="127.0.0.1",
                status="online",
                max_concurrency=1,
                is_active=True,
            )
        )
        self.db.commit()
