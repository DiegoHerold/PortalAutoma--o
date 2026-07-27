from __future__ import annotations

from modules.orchestration.infrastructure.adapters.factory import build_orchestration_adapters


def build_dispatch_adapters(db):
    return build_orchestration_adapters(db)


__all__ = ["build_dispatch_adapters"]
