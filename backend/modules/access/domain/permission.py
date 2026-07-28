from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Permission:
    key: str
    description: str | None = None


LEGACY_CATEGORY_ACTIONS = {
    "can_view": "automation.read",
    "can_execute": "execution.create",
    "can_create": "automation.create",
    "can_edit": "automation.update",
    "can_delete": "automation.update",
    "can_approve": "automation.publish",
}


INITIAL_PERMISSIONS = (
    "automation.read",
    "automation.create",
    "automation.update",
    "automation.publish",
    "automation.block",
    "runtime.read",
    "runtime.manage",
    "agent.read",
    "agent.manage",
    "agent.disable",
    "agent.update",
    "agent.diagnose",
    "execution.read",
    "execution.create",
    "execution.cancel",
    "execution.retry",
    "flow.read",
    "flow.create",
    "flow.update",
    "flow.publish",
    "flow.execute",
    "schedule.read",
    "schedule.create",
    "schedule.update",
    "schedule.trigger",
    "artifact.read",
    "artifact.download",
    "audit.read",
    "secret.read_metadata",
    "secret.manage",
    "admin.users",
    "admin.roles",
    "admin.system",
)

