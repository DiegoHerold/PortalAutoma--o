from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.dispatch.application.ports import AgentCommand, AgentCommandStatus
from modules.dispatch.infrastructure.orm.models import AgentCommandRecord


class SqlAlchemyAgentCommandStore:
    def __init__(self, db: Session) -> None:
        self.db = db

    def append(self, command: AgentCommand) -> None:
        row = AgentCommandRecord(
            id=command.id,
            agent_id=command.agent_id,
            agent_instance_id=command.agent_instance_id,
            command_sequence=command.command_sequence,
            message_type=command.message_type,
            payload=command.payload,
            status=command.status.value,
            created_at=command.created_at,
            available_at=command.available_at or command.created_at,
            sent_at=command.sent_at,
            acknowledged_at=command.acknowledged_at,
            expires_at=command.expires_at,
            attempts=command.attempts,
            last_error=command.last_error,
        )
        self.db.add(row)
        self.db.flush()

    def next_pending_for_agent(self, agent_id: str) -> AgentCommand | None:
        row = self.db.scalar(
            select(AgentCommandRecord)
            .where(AgentCommandRecord.agent_id == agent_id, AgentCommandRecord.status == "pending")
            .order_by(AgentCommandRecord.command_sequence)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        return _to_domain(row) if row else None


def _to_domain(row: AgentCommandRecord) -> AgentCommand:
    return AgentCommand(
        id=row.id,
        agent_id=row.agent_id,
        agent_instance_id=row.agent_instance_id,
        command_sequence=row.command_sequence,
        message_type=row.message_type,
        payload=row.payload,
        status=AgentCommandStatus(row.status),
        created_at=row.created_at,
        available_at=row.available_at,
        sent_at=row.sent_at,
        acknowledged_at=row.acknowledged_at,
        expires_at=row.expires_at,
        attempts=row.attempts,
        last_error=row.last_error,
    )
