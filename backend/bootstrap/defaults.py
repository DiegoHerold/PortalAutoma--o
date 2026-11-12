from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from infrastructure.config import get_settings
from modules.access.application.use_cases import BootstrapAccessDefaults
from modules.access.domain import RoleSlug
from modules.access.infrastructure.adapters import build_access_adapters
from modules.access.infrastructure.orm.models import AccessRoleRecord, AccessUserCategoryPermissionRecord, AccessUserRecord
from modules.catalog.infrastructure.orm.models import CatalogCategoryRecord, RuntimeRecord, RuntimeVersionRecord
from modules.fleet.infrastructure.orm.models import FleetWorkerRecord
from modules.governance.application.use_cases import BootstrapGovernanceDefaults
from modules.governance.infrastructure.adapters import build_governance_adapters
from modules.access.infrastructure.hashing import PasslibPasswordHasher


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
        self.passwords = PasslibPasswordHasher()

    def ensure_defaults(self) -> None:
        self._ensure_roles()
        self._ensure_categories()
        self._ensure_admin()
        # Permissões por categoria soltas na pessoa saíram (12/11/2026): o admin vê tudo pelo papel.
        self._ensure_access_governance_defaults()
        self._ensure_default_runtimes()
        self._ensure_default_worker()

    def _ensure_roles(self) -> None:
        default_roles = (
            (RoleSlug.ADMIN.value, "Admin", "Full platform access."),
            (RoleSlug.MANAGER.value, "Manager", "Operational management with limits."),
            (RoleSlug.OPERATOR.value, "Operator", "Execution and operational usage."),
            (RoleSlug.VIEWER.value, "Viewer", "Read only access."),
        )
        for slug, name, description in default_roles:
            if self.db.scalar(select(AccessRoleRecord).where(AccessRoleRecord.slug == slug)):
                continue
            self.db.add(AccessRoleRecord(name=name, slug=slug, description=description, status="active", is_system=True))
        self.db.commit()

    def _ensure_categories(self) -> None:
        for slug, name in DEFAULT_CATEGORIES:
            if self.db.scalar(select(CatalogCategoryRecord).where(CatalogCategoryRecord.slug == slug)):
                continue
            self.db.add(CatalogCategoryRecord(name=name, slug=slug, description=f"{name} automations", is_active=True))
        self.db.commit()

    def _ensure_admin(self) -> None:
        if self.db.scalar(select(AccessUserRecord).where(AccessUserRecord.email == self.settings.first_superuser_email)):
            return
        admin_role = self.db.scalar(select(AccessRoleRecord).where(AccessRoleRecord.slug == RoleSlug.ADMIN.value))
        if admin_role is None:
            raise RuntimeError("Admin role must exist before creating the default user.")
        self.db.add(
            AccessUserRecord(
                name=self.settings.first_superuser_name,
                email=self.settings.first_superuser_email,
                password_hash=self.passwords.hash(self.settings.first_superuser_password),
                role_id=admin_role.id,
                is_active=True,
                status="active",
            )
        )
        self.db.commit()

    def _ensure_admin_permissions(self) -> None:
        admin = self.db.scalar(select(AccessUserRecord).where(AccessUserRecord.email == self.settings.first_superuser_email))
        if admin is None:
            return
        categories = self.db.scalars(select(CatalogCategoryRecord).order_by(CatalogCategoryRecord.name)).all()
        existing_category_ids = set(
            self.db.scalars(
                select(AccessUserCategoryPermissionRecord.category_id).where(AccessUserCategoryPermissionRecord.user_id == admin.id)
            ).all()
        )
        for category in categories:
            if category.id in existing_category_ids:
                continue
            self.db.add(
                AccessUserCategoryPermissionRecord(
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

    def _ensure_access_governance_defaults(self) -> None:
        access_adapters = build_access_adapters(self.db)
        BootstrapAccessDefaults(access_adapters.access, access_adapters.transaction).execute()
        default_org = next((org for org in access_adapters.access.list_organizations() if org.key == "default"), None)
        admin = access_adapters.access.get_user_by_email(self.settings.first_superuser_email)
        if default_org is not None and admin is not None and admin.organization_id is None:
            access_adapters.access.update_user(admin.id, {"organization_id": default_org.id})
            access_adapters.transaction.commit()

        governance_adapters = build_governance_adapters(self.db)
        BootstrapGovernanceDefaults(governance_adapters.governance, governance_adapters.transaction).execute()

    def _ensure_default_worker(self) -> None:
        worker = self.db.scalar(select(FleetWorkerRecord).where(FleetWorkerRecord.hostname == "local-simulated-worker"))
        if worker:
            return
        self.db.add(
            FleetWorkerRecord(
                name="Local Simulated Worker",
                hostname="local-simulated-worker",
                ip_address="127.0.0.1",
                status="online",
                max_concurrency=1,
                is_active=True,
            )
        )
        self.db.commit()

    def _ensure_default_runtimes(self) -> None:
        defaults = (
            ("python-desktop", "Python Desktop", "Interactive Python automation runtime."),
            ("python-background", "Python Background", "Headless/background Python automation runtime."),
            ("powershell-standard", "PowerShell Standard", "PowerShell automation runtime."),
            ("node-browser", "Node Browser", "Node.js browser automation runtime."),
            ("standalone-executable", "Standalone Executable", "Prebuilt executable runtime."),
        )
        for key, name, description in defaults:
            runtime = self.db.scalar(select(RuntimeRecord).where(RuntimeRecord.key == key))
            if runtime is None:
                runtime = RuntimeRecord(id=str(uuid4()), key=key, name=name, description=description, status="active")
                self.db.add(runtime)
                self.db.flush()
            for version in ("1", "1.0.0"):
                existing_version = self.db.scalar(
                    select(RuntimeVersionRecord).where(
                        RuntimeVersionRecord.runtime_id == runtime.id,
                        RuntimeVersionRecord.version == version,
                        RuntimeVersionRecord.operating_system == "windows",
                        RuntimeVersionRecord.architecture == "x64",
                    )
                )
                if existing_version is None:
                    self.db.add(
                        RuntimeVersionRecord(
                            id=str(uuid4()),
                            runtime_id=runtime.id,
                            version=version,
                            operating_system="windows",
                            architecture="x64",
                            status="published",
                            minimum_agent_version=None,
                            supported_entrypoints=["python-function", "powershell-script", "executable"],
                            supported_execution_modes=["interactive", "background"],
                            metadata_json={"seeded": True},
                        )
                    )
        self.db.commit()
