from datetime import UTC, datetime


def build_heartbeat_payload(worker_name: str) -> dict:
    return {"worker_name": worker_name, "timestamp": datetime.now(UTC).isoformat()}
