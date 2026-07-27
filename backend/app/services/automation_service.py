from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.permissions import is_admin
from app.models.user import User
from app.schemas.automation import AutomationCreate, AutomationUpdate
from app.services.permission_service import PermissionService
from modules.catalog.application.dto import ActorDTO, AutomationDTO
from modules.catalog.application.use_cases import (
    ArchiveAutomation,
    CreateAutomation,
    GetAutomation,
    ListAutomations,
    UpdateAutomationMetadata,
)
from modules.catalog.domain.errors import CatalogValidationError
from modules.catalog.infrastructure.adapters import build_catalog_adapters


class AutomationHasActiveJobsError(Exception):
    """Compatibility exception kept for legacy routes."""


class AutomationService:
    """Compatibility facade for legacy `/automations` routes.

    Catalog rules live in `backend/modules/catalog`; this class only applies the
    still-legacy Access checks and translates old schemas to module DTOs.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.permissions = PermissionService(db)
        self.adapters = build_catalog_adapters(db)

    def list_automations(self, user: User) -> list[AutomationDTO]:
        automations = ListAutomations(self.adapters.catalog).execute()
        if is_admin(user):
            return automations
        allowed_category_ids = {
            permission.category_id for permission in user.category_permissions if permission.can_view
        }
        return [automation for automation in automations if automation.category_id in allowed_category_ids]

    def create_automation(self, user: User, payload: AutomationCreate) -> AutomationDTO:
        self.permissions.ensure_category_action(user, payload.category_id, "can_create")
        return CreateAutomation(
            self.adapters.catalog,
            self.adapters.audit,
            self.adapters.outbox,
            self.adapters.transaction,
        ).execute(payload.model_dump(), _actor(user))

    def update_automation(self, user: User, automation_id: int, payload: AutomationUpdate) -> AutomationDTO:
        automation = self.get_automation(user, automation_id)
        self.permissions.ensure_category_action(user, automation.category_id, "can_edit")
        return UpdateAutomationMetadata(
            self.adapters.catalog,
            self.adapters.audit,
            self.adapters.outbox,
            self.adapters.transaction,
        ).execute(automation_id, payload.model_dump(), _actor(user))

    def delete_automation(self, user: User, automation_id: int) -> None:
        automation = self.get_automation(user, automation_id)
        self.permissions.ensure_category_action(user, automation.category_id, "can_delete")
        ArchiveAutomation(
            self.adapters.catalog,
            self.adapters.audit,
            self.adapters.outbox,
            self.adapters.transaction,
        ).execute(automation_id, _actor(user))

    def get_automation(self, user: User, automation_id: int) -> AutomationDTO:
        try:
            automation = GetAutomation(self.adapters.catalog).execute(automation_id)
        except CatalogValidationError as exc:
            raise ValueError(str(exc)) from exc
        if is_admin(user):
            return automation
        allowed_category_ids = {
            permission.category_id for permission in user.category_permissions if permission.can_view
        }
        if automation.category_id not in allowed_category_ids:
            raise ValueError("Automation not found.")
        return automation


def _actor(user: User) -> ActorDTO:
    return ActorDTO(actor_type="user", actor_id=str(user.id), actor_email=user.email)
