"""
Ephemeral storage for "reviewed but not yet confirmed" automation imports —
backs the preview/confirm step shared by both the GitHub and manual ZIP
import flows (section 3 of the task: both origins converge on the same
Automation/AutomationSource/AutomationVersion result).

Backed by Redis (already part of the stack for Celery) with a TTL, so an
unconfirmed import simply expires instead of leaking state. NOTE: the
associated package ZIP is already written to permanent storage by the time
it's staged here; if the staging entry expires without confirmation, the
orphaned object is not automatically cleaned up yet — see
docs/automation-catalog.md "Limitações conhecidas".
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import redis

from app.core.config import get_settings

STAGING_KEY_PREFIX = "automation_import_staging:"


def _client() -> redis.Redis:
    settings = get_settings()
    return redis.from_url(settings.redis_url, decode_responses=True)


def create_staging_entry(payload: dict[str, Any]) -> str:
    settings = get_settings()
    staging_id = f"stg_{uuid.uuid4().hex[:24]}"
    _client().set(
        f"{STAGING_KEY_PREFIX}{staging_id}",
        json.dumps(payload, ensure_ascii=False),
        ex=settings.import_staging_ttl_seconds,
    )
    return staging_id


def get_staging_entry(staging_id: str) -> dict[str, Any] | None:
    raw = _client().get(f"{STAGING_KEY_PREFIX}{staging_id}")
    if raw is None:
        return None
    return json.loads(raw)


def delete_staging_entry(staging_id: str) -> None:
    _client().delete(f"{STAGING_KEY_PREFIX}{staging_id}")
