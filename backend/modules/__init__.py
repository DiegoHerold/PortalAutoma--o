from __future__ import annotations

from modules.shared.context import PortalContext

PORTAL_CONTEXTS: tuple[PortalContext, ...] = (
    PortalContext(
        name="access",
        responsibilities=("users", "organizations", "teams", "auth", "sessions", "roles", "permissions"),
        owns=("User", "Organization", "Team", "Role", "Permission", "Session"),
    ),
    PortalContext(
        name="catalog",
        responsibilities=("automations", "versions", "manifests", "packages", "runtimes", "publication"),
        owns=("Automation", "AutomationVersion", "AutomationManifest", "AutomationPackage", "Runtime", "RuntimeVersion"),
    ),
    PortalContext(
        name="fleet",
        responsibilities=("agents", "instances", "capabilities", "machine_profile", "capacity", "pools"),
        owns=(
            "Agent",
            "AgentInstance",
            "AgentCapability",
            "AgentMachineProfile",
            "AgentResourceSnapshot",
            "AgentCapacityRecommendation",
            "AgentConfiguration",
        ),
    ),
    PortalContext(
        name="orchestration",
        responsibilities=("executions", "tasks", "attempts", "flows", "schedules", "results"),
        owns=("Execution", "TaskExecution", "ExecutionAttempt", "Flow", "FlowVersion", "FlowExecution", "Schedule", "ScheduleExecution"),
    ),
    PortalContext(
        name="dispatch",
        responsibilities=("scheduler", "offers", "reservations", "commits", "locks", "leases"),
        owns=("ExecutionOffer", "ResourceReservation", "ResourceLock", "ExecutionLease"),
    ),
    PortalContext(
        name="telemetry",
        responsibilities=("events", "logs", "metrics", "sequences", "ack", "timeline", "realtime"),
        owns=("ExecutionEvent", "ExecutionLog", "ExecutionMetric", "EventAcknowledgement"),
    ),
    PortalContext(
        name="storage",
        responsibilities=("artifacts", "uploads", "downloads", "stored_objects", "retention"),
        owns=("Artifact", "UploadSession", "StoredObject"),
    ),
    PortalContext(
        name="governance",
        responsibilities=("secrets", "audit", "policies", "limits", "security", "retention"),
        owns=("Secret", "SecretVersion", "SecretGrant", "AuditEvent"),
    ),
)

