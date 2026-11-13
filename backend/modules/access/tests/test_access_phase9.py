from __future__ import annotations

from modules.access.application.dto import OrganizationDTO, ServiceAccountDTO, TeamDTO
from modules.access.application.use_cases import CreateOrganization, CreateTeam, DeleteOrganization, DeleteTeam, UpdateOrganization, UpdateTeam


class AdminActor:
    id = 7
    role = "admin"


class AccessStub:
    def __init__(self) -> None:
        self.organization_payload: dict | None = None
        self.team_payload: dict | None = None
        self.service_account_payload: dict | None = None
        self.deleted: list[tuple[str, int | str]] = []

    def create_organization(self, payload: dict) -> OrganizationDTO:
        self.organization_payload = payload
        return OrganizationDTO(1, payload["key"], payload["name"], payload["status"], None, None)

    def create_team(self, payload: dict) -> TeamDTO:
        self.team_payload = payload
        return TeamDTO(2, payload["organization_id"], payload["key"], payload["name"], payload["status"], None, None)

    def update_organization(self, organization_id: int, payload: dict) -> OrganizationDTO:
        self.organization_payload = payload
        return OrganizationDTO(organization_id, payload["key"], payload["name"], payload["status"], None, None)

    def delete_organization(self, organization_id: int) -> None:
        self.deleted.append(("organization", organization_id))

    def update_team(self, team_id: int, payload: dict) -> TeamDTO:
        self.team_payload = payload
        return TeamDTO(team_id, payload["organization_id"], payload["key"], payload["name"], payload["status"], None, None)

    def delete_team(self, team_id: int) -> None:
        self.deleted.append(("team", team_id))

    def update_service_account(self, service_account_id: str, payload: dict) -> ServiceAccountDTO:
        self.service_account_payload = payload
        return ServiceAccountDTO(service_account_id, payload.get("organization_id"), payload["name"], "active", payload["permissions"], None, payload.get("expires_at"), None, None)

    def delete_service_account(self, service_account_id: str) -> None:
        self.deleted.append(("service_account", service_account_id))


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


def test_create_organization_audits_the_real_creation_payload() -> None:
    repository = AccessStub()
    audit = AuditStub()
    transaction = TransactionStub()

    organization = CreateOrganization(repository, audit, transaction).execute(
        AdminActor(), {"key": "biason", "name": "Biason", "status": "active"}
    )

    assert organization.key == "biason"
    assert repository.organization_payload == {"key": "biason", "name": "Biason", "status": "active"}
    assert audit.events[0].action == "organization_created"
    assert transaction.commits == 1


def test_create_team_requires_an_organization_payload_and_audits_it() -> None:
    repository = AccessStub()
    audit = AuditStub()
    transaction = TransactionStub()

    team = CreateTeam(repository, audit, transaction).execute(
        AdminActor(), {"organization_id": 1, "key": "operations", "name": "Operations", "status": "active"}
    )

    assert team.organization_id == 1
    assert repository.team_payload is not None
    assert audit.events[0].resource_type == "team"
    assert transaction.commits == 1


def test_update_access_resources_audits_the_change() -> None:
    repository = AccessStub()
    audit = AuditStub()
    transaction = TransactionStub()

    organization = UpdateOrganization(repository, audit, transaction).execute(AdminActor(), 1, {"key": "biason", "name": "Biason", "status": "disabled"})
    team = UpdateTeam(repository, audit, transaction).execute(AdminActor(), 2, {"organization_id": 1, "key": "ops", "name": "Operations", "status": "active"})

    assert organization.status == "disabled"
    assert team.key == "ops"
    assert [event.action for event in audit.events] == ["organization_updated", "team_updated"]
    assert transaction.commits == 2


def test_delete_access_resources_audits_the_removal() -> None:
    repository = AccessStub()
    audit = AuditStub()
    transaction = TransactionStub()

    DeleteOrganization(repository, audit, transaction).execute(AdminActor(), 1)
    DeleteTeam(repository, audit, transaction).execute(AdminActor(), 2)

    assert repository.deleted == [("organization", 1), ("team", 2)]
    assert [event.action for event in audit.events] == ["organization_deleted", "team_deleted"]
    assert transaction.commits == 2
