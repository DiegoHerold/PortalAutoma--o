from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from gateway.agent_gateway.errors import EnvelopeValidationFailed, MessageTooLarge, MessageTypeUnsupported
from gateway.agent_gateway.limits import GatewayLimits
from modules.fleet.application.dto import AgentDiagnosticDTO
from modules.fleet.application.use_cases import (
    AcknowledgeAgentCommand,
    RecordAgentCapabilities,
    RecordAgentCapacity,
    RecordAgentHeartbeat,
    RecordAgentMachineProfile,
)
from modules.fleet.application.use_cases._shared import apply_agent_update, new_id, utcnow
from modules.fleet.domain.errors import FleetError
from modules.fleet.infrastructure.adapters import build_fleet_adapters
from modules.dispatch.application.dto import LeaseRenewalCommand
from modules.dispatch.application.use_cases import (
    AcceptExecutionOffer,
    ActivateAttemptDispatchResources,
    CommitExecutionOffer,
    ReconcileAgentSyncState,
    ReconcileExpiredLeases,
    RejectExecutionOffer,
    ReleaseAttemptDispatchResources,
    RenewExecutionLease,
    ScheduleTaskExecution,
)
from modules.dispatch.application.dto import AgentSyncStateCommand
from modules.dispatch.domain.errors import DispatchError
from modules.orchestration.application.use_cases import (
    HandleExecutionCancelled,
    HandleExecutionCompleted,
    HandleExecutionFailed,
    HandleExecutionStarted,
    HandleExecutionTimedOut,
)
from modules.orchestration.domain.errors import OrchestrationError
from modules.orchestration.infrastructure.adapters import build_orchestration_adapters
from modules.dispatch.infrastructure.adapters import build_dispatch_adapters
from modules.storage.application.dto import (
    CompleteArtifactUploadCommand,
    FailArtifactUploadCommand,
    InitiateArtifactUploadCommand,
    to_payload as storage_payload,
)
from modules.storage.application.use_cases import CompleteArtifactUpload, FailArtifactUpload, InitiateArtifactUpload
from modules.storage.domain.errors import StorageError
from modules.storage.infrastructure.adapters import build_storage_adapters
from modules.telemetry.application.dto import EventBatchCommand, to_payload as telemetry_payload
from modules.telemetry.application.use_cases import IngestExecutionEventBatch
from modules.telemetry.domain.errors import TelemetryError
from modules.telemetry.infrastructure.adapters import build_telemetry_adapters
from modules.telemetry.infrastructure.repositories.sqlalchemy_inbox import InboxPayloadConflictError


SUPPORTED_AGENT_MESSAGES = {
    "agent.connected",
    "agent.resumed",
    "agent.heartbeat",
    "agent.profile.updated",
    "agent.capacity.updated",
    "agent.capabilities.updated",
    "agent.diagnostic.result",
    "agent.sync_state",
    "agent.update.progress",
    "agent.command.ack",
    "execution.accepted",
    "execution.rejected",
    "execution.lease.renew",
    "execution.started",
    "execution.event.batch",
    "execution.completed",
    "execution.failed",
    "execution.cancelled",
    "execution.timed_out",
    "artifact.created",
    "artifact.uploaded",
    "artifact.failed",
}

DEFERRED_EXECUTION_MESSAGES = {
    "execution.recovered",
}


def validate_envelope(envelope: dict[str, Any], authenticated_agent_id: str, agent_instance_id: str, protocol_version: str, limits: GatewayLimits) -> None:
    required = ["protocol_version", "message_id", "message_type", "sent_at", "agent_id", "agent_instance_id", "payload"]
    missing = [field for field in required if field not in envelope]
    if missing:
        raise EnvelopeValidationFailed(f"Envelope is missing fields: {', '.join(missing)}.")
    if envelope["protocol_version"] != protocol_version:
        raise EnvelopeValidationFailed("Envelope protocol version differs from negotiated protocol.")
    if envelope["agent_id"] != authenticated_agent_id:
        raise EnvelopeValidationFailed("Agent cannot send messages for another Agent.")
    if envelope["agent_instance_id"] != agent_instance_id:
        raise EnvelopeValidationFailed("Message AgentInstance differs from the active connection.")
    if not isinstance(envelope.get("payload"), dict):
        raise EnvelopeValidationFailed("Envelope payload must be an object.")
    sent_at = _parse_sent_at(envelope.get("sent_at"))
    if abs((datetime.utcnow() - sent_at).total_seconds()) > 300:
        raise EnvelopeValidationFailed("Envelope timestamp is outside the accepted replay window.")
    if envelope["message_type"] == "agent.heartbeat" and _rough_size(envelope["payload"]) > limits.max_heartbeat_payload_bytes:
        raise MessageTooLarge("Heartbeat payload is too large.")
    if envelope["message_type"] == "agent.capabilities.updated":
        capabilities = envelope["payload"].get("capabilities") or []
        if len(capabilities) > limits.max_capabilities_per_message:
            raise MessageTooLarge("Capabilities payload has too many items.")


def route_agent_message(db: Session, envelope: dict[str, Any], protocol_version: str, limits: GatewayLimits) -> dict[str, Any]:
    adapters = build_fleet_adapters(db)
    agent_id = envelope["agent_id"]
    agent_instance_id = envelope["agent_instance_id"]
    message_type = envelope["message_type"]
    payload = envelope["payload"]

    if message_type in DEFERRED_EXECUTION_MESSAGES or message_type not in SUPPORTED_AGENT_MESSAGES:
        raise MessageTypeUnsupported("MESSAGE_TYPE_NOT_SUPPORTED")

    try:
        is_new = adapters.inbox.record_once(envelope["message_id"], "agent", agent_id, message_type, envelope)
    except InboxPayloadConflictError as exc:
        raise EnvelopeValidationFailed(str(exc)) from exc
    if not is_new:
        try:
            if message_type == "artifact.created":
                result = _handle_artifact_created(db, agent_id, agent_instance_id, payload)
                return {"ok": True, "duplicate": True, "message_id": envelope["message_id"], "message_type": message_type, "result": _json(result)}
            if message_type == "artifact.uploaded":
                result = _handle_artifact_uploaded(db, agent_id, agent_instance_id, payload)
                return {"ok": True, "duplicate": True, "message_id": envelope["message_id"], "message_type": message_type, "result": _json(result)}
            if message_type == "artifact.failed":
                result = _handle_artifact_failed(db, agent_id, agent_instance_id, payload)
                return {"ok": True, "duplicate": True, "message_id": envelope["message_id"], "message_type": message_type, "result": _json(result)}
            adapters.transaction.commit()
            return {"ok": True, "duplicate": True, "message_id": envelope["message_id"]}
        except (StorageError, ValueError) as exc:
            adapters.transaction.rollback()
            raise EnvelopeValidationFailed(str(exc)) from exc

    try:
        if message_type == "agent.heartbeat":
            result = RecordAgentHeartbeat(adapters.agents, adapters.instances, adapters.snapshots, adapters.interactive_sessions, adapters.pools, adapters.configurations, adapters.outbox, adapters.transaction).execute(agent_id, agent_instance_id, payload)
        elif message_type == "agent.profile.updated":
            result = RecordAgentMachineProfile(adapters.agents, adapters.profiles, adapters.outbox, adapters.transaction).execute(agent_id, agent_instance_id, payload)
        elif message_type == "agent.capabilities.updated":
            result = RecordAgentCapabilities(adapters.agents, adapters.capabilities, adapters.outbox, adapters.transaction).execute(agent_id, agent_instance_id, payload)
        elif message_type == "agent.capacity.updated":
            result = RecordAgentCapacity(adapters.agents, adapters.pools, adapters.configurations, adapters.outbox, adapters.transaction).execute(agent_id, agent_instance_id, payload)
        elif message_type == "agent.command.ack":
            result = AcknowledgeAgentCommand(adapters.commands, adapters.outbox, adapters.transaction).execute(agent_id, payload)
        elif message_type == "agent.diagnostic.result":
            result = _record_diagnostic_result(adapters, agent_id, agent_instance_id, payload)
        elif message_type == "agent.sync_state":
            result = _handle_agent_sync_state(db, agent_id, agent_instance_id, payload)
        elif message_type == "agent.update.progress":
            result = _record_update_progress(adapters, agent_id, payload)
        elif message_type == "execution.accepted":
            result = _handle_execution_accepted(db, agent_id, agent_instance_id, payload)
        elif message_type == "execution.rejected":
            result = _handle_execution_rejected(db, agent_id, agent_instance_id, payload)
        elif message_type == "execution.lease.renew":
            result = _handle_execution_lease_renew(db, agent_id, agent_instance_id, payload)
        elif message_type == "execution.started":
            result = _handle_execution_started(db, agent_id, agent_instance_id, payload)
        elif message_type == "execution.event.batch":
            result = _handle_execution_event_batch(db, agent_id, agent_instance_id, payload, envelope)
        elif message_type in {"execution.completed", "execution.failed", "execution.cancelled", "execution.timed_out"}:
            result = _handle_execution_terminal(db, agent_id, agent_instance_id, message_type, payload, envelope)
        elif message_type == "artifact.created":
            result = _handle_artifact_created(db, agent_id, agent_instance_id, payload)
        elif message_type == "artifact.uploaded":
            result = _handle_artifact_uploaded(db, agent_id, agent_instance_id, payload)
        elif message_type == "artifact.failed":
            result = _handle_artifact_failed(db, agent_id, agent_instance_id, payload)
        elif message_type in {"agent.connected", "agent.resumed"}:
            result = {"ok": True, "pending_commands": [item.id for item in adapters.commands.pending_for_agent(agent_id, limits.max_pending_commands_per_agent)]}
            adapters.transaction.commit()
        else:
            raise MessageTypeUnsupported("MESSAGE_TYPE_NOT_SUPPORTED")
        adapters.inbox.mark_processed(envelope["message_id"])
        adapters.transaction.commit()
        return {"ok": True, "message_id": envelope["message_id"], "message_type": message_type, "result": _json(result)}
    except (FleetError, OrchestrationError, DispatchError, TelemetryError, StorageError, ValueError) as exc:
        adapters.transaction.rollback()
        raise EnvelopeValidationFailed(str(exc)) from exc


def _handle_execution_accepted(db: Session, agent_id: str, agent_instance_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    _require_payload_fields(payload, ["execution_offer_id", "execution_attempt_id", "agent_id", "agent_instance_id", "accepted_at"])
    _ensure_payload_agent(payload, agent_id, agent_instance_id)
    offer_id = str(payload.get("execution_offer_id") or "")
    attempt_id = str(payload.get("execution_attempt_id") or "")
    adapters = build_dispatch_adapters(db)
    accepted = AcceptExecutionOffer(
        adapters.attempts,
        adapters.offers,
        adapters.commands,
        adapters.outbox,
        adapters.transaction,
    ).execute(offer_id=offer_id, attempt_id=attempt_id, agent_id=agent_id, agent_instance_id=agent_instance_id)
    committed = CommitExecutionOffer(
        adapters.attempts,
        adapters.offers,
        adapters.leases,
        adapters.commands,
        adapters.outbox,
        adapters.transaction,
    ).execute(offer_id=offer_id, attempt_id=attempt_id, agent_id=agent_id, agent_instance_id=agent_instance_id)
    return {"execution_offer_id": accepted.id, "status": accepted.status, "commit_command_id": committed.get("command_id")}


def _handle_execution_rejected(db: Session, agent_id: str, agent_instance_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    _require_payload_fields(payload, ["execution_offer_id", "execution_attempt_id", "agent_id", "agent_instance_id", "rejection_code", "rejected_at"])
    _ensure_payload_agent(payload, agent_id, agent_instance_id)
    adapters = build_dispatch_adapters(db)
    offer = RejectExecutionOffer(
        adapters.attempts,
        adapters.tasks,
        adapters.offers,
        adapters.reservations,
        adapters.locks,
        adapters.commands,
        adapters.outbox,
        adapters.transaction,
    ).execute(
        offer_id=str(payload.get("execution_offer_id") or ""),
        attempt_id=str(payload.get("execution_attempt_id") or ""),
        agent_id=agent_id,
        agent_instance_id=agent_instance_id,
        rejection_code=str(payload.get("rejection_code") or ""),
        rejection_details=payload.get("rejection_details") if isinstance(payload.get("rejection_details"), dict) else {},
    )
    redistribution = ScheduleTaskExecution(
        adapters.ready_tasks,
        adapters.attempts,
        adapters.offers,
        adapters.automation_versions,
        adapters.candidates,
        adapters.decisions,
        adapters.reservations,
        adapters.locks,
        adapters.commands,
        adapters.outbox,
        adapters.transaction,
    ).execute(str(payload.get("task_execution_id") or _attempt_task_id(adapters, offer.execution_attempt_id)))
    return {"execution_offer_id": offer.id, "status": offer.status, "rejection_code": offer.rejection_code, "redistribution": _json(redistribution)}


def _handle_execution_started(db: Session, agent_id: str, agent_instance_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    _require_payload_fields(payload, ["execution_attempt_id", "agent_id", "agent_instance_id", "started_at"])
    _ensure_payload_agent(payload, agent_id, agent_instance_id)
    dispatch_adapters = build_dispatch_adapters(db)
    ActivateAttemptDispatchResources(dispatch_adapters.reservations, dispatch_adapters.outbox, dispatch_adapters.transaction).execute(
        str(payload.get("execution_attempt_id") or ""),
        offer_id=str(payload.get("execution_offer_id") or "") or None,
    )
    adapters = build_orchestration_adapters(db)
    details = HandleExecutionStarted(
        adapters.executions,
        adapters.tasks,
        adapters.attempts,
        adapters.offers,
        adapters.reservations,
        adapters.outbox,
        adapters.transaction,
    ).execute(
        attempt_id=str(payload.get("execution_attempt_id") or ""),
        offer_id=str(payload.get("execution_offer_id") or "") or None,
        agent_id=agent_id,
        agent_instance_id=agent_instance_id,
        started_at=payload.get("started_at"),
    )
    return {"execution_id": details.execution.id, "execution_attempt_id": details.current_attempt.id if details.current_attempt else None, "status": details.execution.status}


def _handle_execution_lease_renew(db: Session, agent_id: str, agent_instance_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    _require_payload_fields(payload, ["execution_attempt_id", "lease_id", "renewal_sequence"])
    adapters = build_dispatch_adapters(db)
    lease = RenewExecutionLease(adapters.attempts, adapters.leases, adapters.outbox, adapters.transaction).execute(
        LeaseRenewalCommand(
            execution_attempt_id=str(payload.get("execution_attempt_id") or ""),
            lease_id=str(payload.get("lease_id") or ""),
            renewal_sequence=int(payload.get("renewal_sequence") or 0),
            running=bool(payload.get("running", True)),
            observed_at=_parse_optional_datetime(payload.get("observed_at")),
            agent_id=agent_id,
            agent_instance_id=agent_instance_id,
        )
    )
    return {"lease_id": lease.id, "status": lease.status, "expires_at": lease.expires_at.isoformat(), "renewal_sequence": lease.renewal_sequence}


def _handle_agent_sync_state(db: Session, agent_id: str, agent_instance_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    adapters = build_dispatch_adapters(db)
    result = ReconcileAgentSyncState(
        adapters.executions,
        adapters.tasks,
        adapters.attempts,
        adapters.offers,
        adapters.reservations,
        adapters.locks,
        adapters.leases,
        adapters.automation_versions,
        adapters.reconciliations,
        adapters.outbox,
        adapters.transaction,
    ).execute(AgentSyncStateCommand(agent_id=agent_id, agent_instance_id=agent_instance_id, payload=payload))
    return _json(result)


def _handle_execution_event_batch(db: Session, agent_id: str, agent_instance_id: str, payload: dict[str, Any], envelope: dict[str, Any]) -> dict[str, Any]:
    _require_payload_fields(payload, ["execution_attempt_id", "events"])
    adapters = build_telemetry_adapters(db)
    ack = IngestExecutionEventBatch(
        adapters.attempts,
        adapters.events,
        adapters.acknowledgements,
        adapters.metrics,
        adapters.validator,
        adapters.masker,
        adapters.realtime,
        adapters.transaction,
    ).execute(
        EventBatchCommand(
            execution_attempt_id=str(payload.get("execution_attempt_id") or ""),
            events=payload.get("events") if isinstance(payload.get("events"), list) else [],
            agent_id=agent_id,
            agent_instance_id=agent_instance_id,
            message_id=envelope.get("message_id"),
            correlation_id=envelope.get("correlation_id"),
            causation_id=envelope.get("causation_id"),
        )
    )
    return telemetry_payload(ack)


def _handle_execution_terminal(db: Session, agent_id: str, agent_instance_id: str, message_type: str, payload: dict[str, Any], envelope: dict[str, Any]) -> dict[str, Any]:
    _require_payload_fields(payload, ["execution_attempt_id", "event_sequence"])
    telemetry_result = _handle_execution_event_batch(
        db,
        agent_id,
        agent_instance_id,
        {
            "execution_attempt_id": payload["execution_attempt_id"],
            "events": [
                {
                    "event_id": payload.get("event_id") or f"{envelope['message_id']}:{payload['event_sequence']}",
                    "event_sequence": payload["event_sequence"],
                    "event_type": message_type,
                    "occurred_at": payload.get("occurred_at") or payload.get("completed_at") or payload.get("failed_at") or payload.get("cancelled_at") or payload.get("timed_out_at") or envelope.get("sent_at"),
                    "payload": {key: value for key, value in payload.items() if key not in {"event_id", "event_sequence", "occurred_at"}},
                    **({"level": "ERROR"} if message_type in {"execution.failed", "execution.timed_out"} else {}),
                }
            ],
        },
        envelope,
    )
    adapters = build_orchestration_adapters(db)
    use_case_args = (
        adapters.executions,
        adapters.tasks,
        adapters.attempts,
        adapters.offers,
        adapters.reservations,
        adapters.automation_versions,
        adapters.outbox,
        adapters.transaction,
    )
    handler_map = {
        "execution.completed": HandleExecutionCompleted,
        "execution.failed": HandleExecutionFailed,
        "execution.cancelled": HandleExecutionCancelled,
        "execution.timed_out": HandleExecutionTimedOut,
    }
    details = handler_map[message_type](*use_case_args).execute(
        attempt_id=str(payload.get("execution_attempt_id") or ""),
        agent_id=agent_id,
        agent_instance_id=agent_instance_id,
        payload=payload,
    )
    dispatch_adapters = build_dispatch_adapters(db)
    if message_type == "execution.cancelled":
        _complete_cancellation_request(dispatch_adapters, str(payload.get("execution_id") or ""))
    ReleaseAttemptDispatchResources(
        dispatch_adapters.reservations,
        dispatch_adapters.locks,
        dispatch_adapters.leases,
        dispatch_adapters.outbox,
        dispatch_adapters.transaction,
    ).execute(str(payload.get("execution_attempt_id") or ""), message_type)
    dispatch_adapters.transaction.commit()
    return {"telemetry": telemetry_result, "execution": details.to_payload()}


def _complete_cancellation_request(dispatch_adapters, execution_id: str) -> None:
    if not execution_id:
        return
    request = dispatch_adapters.cancellation_requests.current_for_execution(execution_id)
    if request is None:
        return
    dispatch_adapters.cancellation_requests.save(
        replace(request, status="completed", completed_at=utcnow())
    )


def _handle_artifact_created(db: Session, agent_id: str, agent_instance_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    _require_payload_fields(payload, ["execution_attempt_id", "name", "content_type"])
    adapters = build_storage_adapters(db)
    result = InitiateArtifactUpload(
        adapters.artifacts,
        adapters.artifact_uploads,
        adapters.stored_objects,
        adapters.upload_sessions,
        adapters.attempts,
        adapters.object_storage,
        adapters.temporary_urls,
        adapters.transaction,
    ).execute(
        InitiateArtifactUploadCommand(
            execution_attempt_id=str(payload.get("execution_attempt_id") or ""),
            name=str(payload.get("name") or ""),
            content_type=str(payload.get("content_type") or "application/octet-stream"),
            size_bytes=_int_or_none(payload.get("size_bytes")),
            sha256=payload.get("sha256"),
            metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
            artifact_id=payload.get("artifact_id"),
            agent_id=agent_id,
            agent_instance_id=agent_instance_id,
            created_by=agent_id,
        )
    )
    return storage_payload(result)


def _handle_artifact_uploaded(db: Session, agent_id: str, agent_instance_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    _require_payload_fields(payload, ["artifact_id"])
    adapters = build_storage_adapters(db)
    artifact = CompleteArtifactUpload(
        adapters.artifacts,
        adapters.stored_objects,
        adapters.upload_sessions,
        adapters.attempts,
        adapters.object_storage,
        adapters.transaction,
    ).execute(
        CompleteArtifactUploadCommand(
            artifact_id=str(payload.get("artifact_id") or ""),
            execution_attempt_id=payload.get("execution_attempt_id"),
            upload_session_id=payload.get("upload_session_id"),
            size_bytes=_int_or_none(payload.get("size_bytes")),
            sha256=payload.get("sha256"),
            agent_id=agent_id,
            agent_instance_id=agent_instance_id,
        )
    )
    return storage_payload(artifact)


def _handle_artifact_failed(db: Session, agent_id: str, agent_instance_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    _require_payload_fields(payload, ["artifact_id", "reason"])
    adapters = build_storage_adapters(db)
    artifact = FailArtifactUpload(
        adapters.artifacts,
        adapters.upload_sessions,
        adapters.attempts,
        adapters.transaction,
    ).execute(
        FailArtifactUploadCommand(
            artifact_id=str(payload.get("artifact_id") or ""),
            execution_attempt_id=payload.get("execution_attempt_id"),
            upload_session_id=payload.get("upload_session_id"),
            reason=str(payload.get("reason") or ""),
            agent_id=agent_id,
            agent_instance_id=agent_instance_id,
        )
    )
    return storage_payload(artifact)


def _ensure_payload_agent(payload: dict[str, Any], agent_id: str, agent_instance_id: str) -> None:
    if payload.get("agent_id") not in (None, agent_id):
        raise EnvelopeValidationFailed("Payload Agent differs from the authenticated Agent.")
    if payload.get("agent_instance_id") not in (None, agent_instance_id):
        raise EnvelopeValidationFailed("Payload AgentInstance differs from the active connection.")


def _require_payload_fields(payload: dict[str, Any], fields: list[str]) -> None:
    missing = [field for field in fields if payload.get(field) in (None, "")]
    if missing:
        raise EnvelopeValidationFailed(f"Payload is missing fields: {', '.join(missing)}.")


def _record_diagnostic_result(adapters, agent_id: str, agent_instance_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    diagnostic = AgentDiagnosticDTO(
        id=new_id("adg"),
        agent_id=agent_id,
        agent_instance_id=agent_instance_id,
        request_command_id=payload.get("request_command_id") or payload.get("command_id"),
        status=str(payload.get("status") or "completed"),
        summary=payload.get("summary"),
        details=payload.get("details") or {},
        artifact_id=payload.get("artifact_id"),
        requested_at=utcnow(),
        completed_at=utcnow(),
        error=payload.get("error"),
    )
    saved = adapters.diagnostics.add(diagnostic)
    adapters.outbox.append_event("agent.diagnostic.result", agent_id, {"agent_id": agent_id, "diagnostic_id": saved.id})
    return {"diagnostic_id": saved.id, "status": saved.status}


def _record_update_progress(adapters, agent_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    agent = adapters.agents.get(agent_id)
    if agent is None:
        return {"ok": False}
    status = str(payload.get("status") or "")
    current_version = payload.get("current_version") or agent.current_version
    administrative_status = "enabled" if status in {"completed", "succeeded"} else agent.administrative_status
    adapters.agents.save(apply_agent_update(agent, current_version=current_version, administrative_status=administrative_status))
    adapters.outbox.append_event("agent.update.progress", agent_id, {"agent_id": agent_id, "status": status, "progress": payload.get("progress")})
    return {"ok": True, "status": status}


def _parse_sent_at(value: Any) -> datetime:
    if not isinstance(value, str):
        raise EnvelopeValidationFailed("Envelope sent_at must be a date-time string.")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError as exc:
        raise EnvelopeValidationFailed("Envelope sent_at is invalid.") from exc


def _parse_optional_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return None
    return None


def _attempt_task_id(adapters, execution_attempt_id: str) -> str:
    attempt = adapters.attempts.get(execution_attempt_id)
    if attempt is None:
        raise EnvelopeValidationFailed("ExecutionAttempt not found for rejected offer.")
    return attempt.task_execution_id


def _rough_size(payload: dict[str, Any]) -> int:
    return len(str(payload).encode("utf-8"))


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool) or value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _json(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return {key: _json(getattr(value, key)) for key in value.__dataclass_fields__}
    if isinstance(value, dict):
        return {key: _json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    return value
