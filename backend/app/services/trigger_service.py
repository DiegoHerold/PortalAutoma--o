import secrets
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.domain.trigger_mapping import apply_parameter_mapping
from app.models.trigger import Trigger
from app.models.user import User
from app.repositories.automation_repository import AutomationRepository
from app.repositories.trigger_repository import TriggerRepository
from app.schemas.job import JobCreate
from app.schemas.trigger import TriggerCreate, TriggerUpdate
from app.services.audit_service import AuditService
from app.services.job_dispatcher_service import JobDispatcherService
from app.services.permission_service import PermissionService


def _resolved_trigger_fields(payload: TriggerCreate) -> dict:
    """
    A "chained" trigger has no external HTTP endpoint -- route_path/secret_token
    are irrelevant to it, but the Trigger table still requires them (they're
    the real webhook credentials for trigger_type="https"). Auto-generate
    harmless placeholders for chained triggers so the DB constraint is
    satisfied without asking the user to fill in fields that mean nothing
    for this trigger type.
    """
    data = payload.model_dump()
    if payload.trigger_type == "chained":
        data["route_path"] = f"chain/{uuid.uuid4().hex[:12]}"
        data["secret_token"] = secrets.token_urlsafe(24)
    elif data.get("route_path"):
        # Stored bare (no leading "/") so it matches exactly what the
        # {route_path:path} URL segment captures on invocation.
        data["route_path"] = data["route_path"].lstrip("/")
    return data


class TriggerService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.audit = AuditService(db)
        self.triggers = TriggerRepository(db)
        self.automations = AutomationRepository(db)
        self.permissions = PermissionService(db)

    def list_triggers(self) -> list[Trigger]:
        return self.triggers.list_all()

    def create_trigger(self, user: User, payload: TriggerCreate) -> Trigger:
        automation = self.automations.get(payload.automation_id)
        if automation is None:
            raise HTTPException(status_code=404, detail="Automation not found.")
        self.permissions.ensure_category_action(user, automation.category_id, "can_create")
        if payload.trigger_type == "chained":
            source = self.automations.get(payload.source_automation_id)
            if source is None:
                raise HTTPException(status_code=404, detail="Source automation not found.")
        trigger = self.triggers.create(Trigger(**_resolved_trigger_fields(payload)))
        self.audit.record(
            "trigger_created",
            actor_email=user.email,
            resource_type="trigger",
            resource_id=str(trigger.id),
            details=trigger.route_path,
        )
        self.db.commit()
        return trigger

    def update_trigger(self, user: User, trigger_id: int, payload: TriggerUpdate) -> Trigger:
        trigger = self.triggers.get(trigger_id)
        if trigger is None:
            raise ValueError("Trigger not found.")
        current_automation = self.automations.get(trigger.automation_id)
        if current_automation is None:
            raise ValueError("Automation not found.")
        new_automation = self.automations.get(payload.automation_id)
        if new_automation is None:
            raise ValueError("Automation not found.")
        self.permissions.ensure_category_action(user, current_automation.category_id, "can_edit")
        self.permissions.ensure_category_action(user, new_automation.category_id, "can_edit")
        if payload.trigger_type == "chained":
            source = self.automations.get(payload.source_automation_id)
            if source is None:
                raise ValueError("Source automation not found.")
        for field, value in _resolved_trigger_fields(payload).items():
            setattr(trigger, field, value)
        updated = self.triggers.update(trigger)
        self.audit.record(
            "trigger_updated",
            actor_email=user.email,
            resource_type="trigger",
            resource_id=str(updated.id),
            details=updated.route_path,
        )
        self.db.commit()
        return updated

    def delete_trigger(self, user: User, trigger_id: int) -> None:
        trigger = self.triggers.get(trigger_id)
        if trigger is None:
            raise ValueError("Trigger not found.")
        automation = self.automations.get(trigger.automation_id)
        if automation is None:
            raise ValueError("Automation not found.")
        self.permissions.ensure_category_action(user, automation.category_id, "can_delete")
        self.audit.record(
            "trigger_deleted",
            actor_email=user.email,
            resource_type="trigger",
            resource_id=str(trigger.id),
            details=trigger.route_path,
        )
        self.triggers.delete(trigger)

    def dispatch_by_route(
        self,
        route_path: str,
        secret_token: str,
        body: dict,
        headers: dict | None = None,
        query_params: dict | None = None,
    ) -> int:
        trigger = self.triggers.get_by_route_path_normalized(route_path)
        if trigger is None or not trigger.is_active or trigger.secret_token != secret_token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid trigger credentials.")

        automation = self.automations.get(trigger.automation_id)
        if automation is None:
            raise HTTPException(status_code=404, detail="Automation not found.")

        payload_json = apply_parameter_mapping(trigger.parameter_mapping_json, body, headers, query_params)

        job = JobDispatcherService(self.db).dispatch_system(
            JobCreate(
                automation_id=automation.id,
                priority=automation.default_priority,
                payload_json=payload_json,
            ),
            trigger_id=trigger.id,
        )
        self.audit.record(
            "trigger_invoked",
            actor_type="trigger",
            resource_type="trigger",
            resource_id=str(trigger.id),
            details=route_path,
        )
        self.db.commit()
        return job.id

    def preview_mapping(
        self,
        user: User,
        trigger_id: int,
        sample_payload: dict,
        sample_headers: dict | None = None,
        sample_query_params: dict | None = None,
    ) -> dict:
        """
        Dry-run: computes what parameters an automation would receive for a
        sample payload, without dispatching a Job or requiring the trigger's
        secret. Used by the trigger editor UI's "testar" button.
        """
        trigger = self.triggers.get(trigger_id)
        if trigger is None:
            raise ValueError("Trigger not found.")
        automation = self.automations.get(trigger.automation_id)
        if automation is None:
            raise ValueError("Automation not found.")
        self.permissions.ensure_category_action(user, automation.category_id, "can_edit")

        parameters = apply_parameter_mapping(
            trigger.parameter_mapping_json, sample_payload, sample_headers, sample_query_params
        )
        return {"automation_id": automation.id, "parameters": parameters}
