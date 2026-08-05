from __future__ import annotations

from importlib import import_module


_ORM_MODEL_MODULES = (
    "modules.access.infrastructure.orm.models",
    "modules.catalog.infrastructure.orm.models",
    "modules.fleet.infrastructure.orm.models",
    "modules.orchestration.infrastructure.orm.models",
    "modules.orchestration.flows.infrastructure.orm.models",
    "modules.orchestration.scheduling.infrastructure.orm.models",
    "modules.dispatch.infrastructure.orm.models",
    "modules.telemetry.infrastructure.orm.models",
    "modules.storage.infrastructure.orm.models",
    "modules.governance.infrastructure.orm.models",
    "modules.shared.infrastructure.orm.models",
)

_initialized = False


def initialize_orm_metadata() -> None:
    """Import all ORM models that participate in the shared SQLAlchemy metadata."""
    global _initialized
    if _initialized:
        return
    for module_name in _ORM_MODEL_MODULES:
        import_module(module_name)
    _initialized = True
