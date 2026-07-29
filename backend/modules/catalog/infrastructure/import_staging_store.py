from __future__ import annotations

import json
import uuid
from typing import Any

import redis

from infrastructure.config import get_settings

STAGING_KEY_PREFIX = "automation_import_staging:"


def _client() -> redis.Redis:
    return redis.from_url(get_settings().redis_url, decode_responses=True)


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
    return json.loads(raw) if raw is not None else None


def delete_staging_entry(staging_id: str) -> None:
    _client().delete(f"{STAGING_KEY_PREFIX}{staging_id}")
