from enum import StrEnum


class GlobalRoleSlug(StrEnum):
    ADMIN = "admin"
    MANAGER = "manager"
    OPERATOR = "operator"
    VIEWER = "viewer"


class JobPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class JobStatus(StrEnum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkerStatus(StrEnum):
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    DISABLED = "disabled"


class ExecutorType(StrEnum):
    PLAYWRIGHT = "playwright"
    POWER_AUTOMATE = "power_automate"
    N8N = "n8n"
    PYTHON_SCRIPT = "python_script"
    HTTP_REQUEST = "http_request"
    SHELL_COMMAND = "shell_command"


class AutomationSourceType(StrEnum):
    """Origin of an automation's code — GitHub repository or a manual ZIP upload."""

    GITHUB = "github"
    MANUAL_UPLOAD = "manual_upload"


class AutomationVersionStatus(StrEnum):
    """Lifecycle of an immutable AutomationVersion package."""

    VALIDATING = "validating"
    INVALID = "invalid"
    READY = "ready"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
    DISABLED = "disabled"


class AutomationSyncStatus(StrEnum):
    """Whether an AutomationSource is in sync with its upstream (GitHub) origin."""

    SYNCED = "synced"
    UPDATE_AVAILABLE = "update_available"
    ERROR = "error"
    UNKNOWN = "unknown"


class ApplicationPackagingType(StrEnum):
    """How the automation's code is laid out inside application/ in the package."""

    SOURCE = "source"
    WHEEL = "wheel"
