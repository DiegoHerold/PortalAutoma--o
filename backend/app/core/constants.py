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
