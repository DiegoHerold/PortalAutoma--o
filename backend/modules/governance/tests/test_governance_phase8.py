from __future__ import annotations

from datetime import UTC, datetime

from modules.governance.application.dto import SecretDTO, SecretVersionDTO
from modules.governance.application.use_cases import CreateSecret, ListAuditEvents, RotateSecret


class GovernanceRepositoryStub:
    def __init__(self) -> None:
        self.payloads: list[dict] = []

    def create_secret(self, payload: dict) -> tuple[SecretDTO, SecretVersionDTO]:
        self.payloads.append(payload)
        return self._secret("sec-1", "secv-1"), self._version("sec-1", "secv-1", 1)

    def rotate_secret(self, secret_id: str, payload: dict) -> tuple[SecretDTO, SecretVersionDTO]:
        self.payloads.append(payload)
        return self._secret(secret_id, "secv-2"), self._version(secret_id, "secv-2", 2)

    @staticmethod
    def _secret(secret_id: str, version_id: str) -> SecretDTO:
        return SecretDTO(secret_id, 7, "payroll_api", "Payroll API", None, "active", version_id, "42", None, None)

    @staticmethod
    def _version(secret_id: str, version_id: str, version: int) -> SecretVersionDTO:
        return SecretVersionDTO(version_id, secret_id, version, "local-test-key", "42", datetime.now(UTC), None, None)


class CipherStub:
    key_id = "local-test-key"

    def encrypt(self, value: str) -> str:
        return f"encrypted::{len(value)}"


class AuditStub:
    def __init__(self) -> None:
        self.events = []

    def append(self, event):
        self.events.append(event)
        return event


class TransactionStub:
    def __init__(self) -> None:
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1


class Actor:
    id = 42
    organization_id = 7


def test_create_secret_returns_metadata_without_plaintext_value() -> None:
    repository = GovernanceRepositoryStub()
    audit = AuditStub()
    transaction = TransactionStub()

    secret, version = CreateSecret(repository, CipherStub(), audit, transaction).execute(
        Actor(), {"key": "payroll api", "name": "Payroll API", "value": "super-secret-value"}
    )

    assert secret.key == "payroll_api"
    assert version.encryption_key_id == "local-test-key"
    assert not hasattr(secret, "value")
    assert not hasattr(version, "value")
    assert repository.payloads[0]["encrypted_value"] == "encrypted::18"
    assert "super-secret-value" not in str(audit.events[0].after)
    assert transaction.commits == 1


def test_rotate_secret_returns_only_new_version_metadata() -> None:
    repository = GovernanceRepositoryStub()
    audit = AuditStub()
    transaction = TransactionStub()

    secret, version = RotateSecret(repository, CipherStub(), audit, transaction).execute(
        Actor(), "sec-1", {"value": "rotated-secret"}
    )

    assert secret.current_version_id == "secv-2"
    assert version.version == 2
    assert not hasattr(version, "encrypted_value")
    assert "rotated-secret" not in str(audit.events[0].after)
    assert transaction.commits == 1


class AuditListStub:
    def __init__(self) -> None:
        self.filters: dict | None = None

    def list(self, **filters):
        self.filters = filters
        return []


def test_list_audit_events_forwards_structured_filters() -> None:
    repository = AuditListStub()
    since = datetime(2026, 7, 1, tzinfo=UTC)
    until = datetime(2026, 8, 1, tzinfo=UTC)

    events = ListAuditEvents(repository).execute(
        query="artifact",
        actor_type="user",
        resource_type="artifact",
        action="artifact_created",
        occurred_from=since,
        occurred_until=until,
        limit=50,
        offset=100,
    )

    assert events == []
    assert repository.filters == {
        "actor": None,
        "query": "artifact",
        "actor_type": "user",
        "resource_type": "artifact",
        "action": "artifact_created",
        "occurred_from": since,
        "occurred_until": until,
        "limit": 50,
        "offset": 100,
    }
