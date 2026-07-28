from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class CandidateRejectionReason:
    code: str
    message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.code}
        if self.message:
            payload["message"] = self.message
        payload.update(self.details)
        return payload


@dataclass(frozen=True)
class DispatchCandidate:
    agent_id: str
    agent_instance_id: str | None
    eligible: bool
    rejection_reasons: list[CandidateRejectionReason]
    score: float
    score_components: dict[str, float]
    evaluated_at: datetime
    snapshot_revision: int | None = None
    worker_id: int | None = None
    facts: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def pending(cls, *, agent_id: str, agent_instance_id: str | None, worker_id: int | None, evaluated_at: datetime, snapshot_revision: int | None = None) -> "DispatchCandidate":
        return cls(
            agent_id=agent_id,
            agent_instance_id=agent_instance_id,
            worker_id=worker_id,
            eligible=True,
            rejection_reasons=[],
            score=0,
            score_components={},
            evaluated_at=evaluated_at,
            snapshot_revision=snapshot_revision,
        )

    def reject(self, code: str, message: str | None = None, **details: Any) -> "DispatchCandidate":
        return replace(
            self,
            eligible=False,
            rejection_reasons=[*self.rejection_reasons, CandidateRejectionReason(code=code, message=message, details={key: value for key, value in details.items() if value is not None})],
        )

    def with_score(self, score: float, components: dict[str, float]) -> "DispatchCandidate":
        return replace(self, score=score, score_components=components)

    def with_facts(self, facts: dict[str, Any]) -> "DispatchCandidate":
        return replace(self, facts={**self.facts, **facts})

    def to_payload(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_instance_id": self.agent_instance_id,
            "eligible": self.eligible,
            "rejection_reasons": [reason.to_payload() for reason in self.rejection_reasons],
            "score": self.score,
            "score_components": self.score_components,
            "evaluated_at": self.evaluated_at.isoformat(),
            "snapshot_revision": self.snapshot_revision,
            "worker_id": self.worker_id,
            "facts": self.facts,
        }
