from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from gateway.agent_gateway.errors import AuthenticationFailed
from modules.fleet.application.dto import AgentDTO
from modules.fleet.application.use_cases import ValidateAgentCredential
from modules.fleet.domain.errors import FleetError
from modules.fleet.infrastructure.adapters import build_fleet_adapters


@dataclass(frozen=True)
class AuthenticatedAgent:
    agent: AgentDTO
    public_identifier: str


def authenticate_agent(db: Session, authorization: str | None) -> AuthenticatedAgent:
    public_identifier, secret = parse_bearer_credential(authorization)
    if not public_identifier or not secret:
        raise AuthenticationFailed("Agent credential is required.")
    adapters = build_fleet_adapters(db)
    try:
        agent = ValidateAgentCredential(adapters.agents, adapters.credentials, adapters.transaction).execute(public_identifier, secret)
    except FleetError as exc:
        raise AuthenticationFailed(str(exc)) from exc
    return AuthenticatedAgent(agent=agent, public_identifier=public_identifier)


def parse_bearer_credential(authorization: str | None) -> tuple[str | None, str | None]:
    if not authorization:
        return None, None
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or ":" not in value:
        return None, None
    public_identifier, _, secret = value.partition(":")
    return public_identifier.strip(), secret.strip()
