"""Consulta de aplicacao para a Central de Agendamentos (GET /schedules/calendar).

Este modulo NAO produz efeitos de dominio: nunca cria Execution, ScheduleExecution
ou qualquer outro registro. Ele apenas combina:

  Schedule (regra de recorrencia)
    -> ocorrencias futuras/possiveis calculadas em memoria (cron / interval / once)
  ScheduleExecutionRecord (ocorrencia concreta, persistida quando disparada ou pulada)
  Execution / FlowExecution (execucao operacional real, quando existe)

em uma lista unica de "itens de calendario", com status temporal calculado no
servidor (nao no relogio do navegador), estimativa de duracao a partir do
historico real, e agrupamento de sobreposicao para o frontend distribuir em
lanes sem gerar coordenadas de pixel.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from croniter import croniter
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from modules.access.infrastructure.orm.models import AccessUserRecord
from modules.catalog.infrastructure.orm.models import CatalogAutomationRecord, CatalogAutomationVersionRecord
from modules.fleet.infrastructure.orm.models import AgentRecord
from modules.orchestration.flows.infrastructure.orm.models import (
    FlowExecutionRecord,
    FlowNodeExecutionRecord,
    FlowRecord,
    FlowVersionRecord,
)
from modules.orchestration.infrastructure.orm.models import (
    ExecutionAttemptRecord,
    OrchestrationExecutionRecord,
    TaskExecutionRecord,
)
from modules.orchestration.scheduling.application.dto import (
    ScheduleCalendarDensityBucketDTO,
    ScheduleCalendarItemDTO,
    ScheduleCalendarProgressDTO,
    ScheduleCalendarRangeDTO,
    ScheduleCalendarResultDTO,
    ScheduleCalendarSummaryDTO,
    ScheduleDTO,
)
from modules.orchestration.scheduling.domain import aware, timezone_or_default
from modules.orchestration.scheduling.infrastructure.orm.models import Schedule, ScheduleExecutionRecord

MAX_RANGE_DAYS = 93
MAX_SCHEDULES = 500
MAX_OCCURRENCES_PER_SCHEDULE = 500
MIN_VISUAL_WIDTH_SECONDS = 15 * 60
ACTIVE_SCHEDULE_EXECUTION_STATUSES = {"created", "running"}
DURATION_HISTORY_SAMPLE = 20
FINISHED_EXECUTION_STATUSES = {"succeeded", "partially_succeeded", "failed", "cancelled", "timed_out"}


class CalendarQueryError(ValueError):
    pass


# --------------------------------------------------------------------------------------
# Funcoes puras (sem I/O) - cobertas por testes unitarios diretos.
# --------------------------------------------------------------------------------------


def occurrences_in_window(schedule: ScheduleDTO, window_start: datetime, window_end: datetime) -> list[datetime]:
    """Calcula ocorrencias possiveis de um Schedule dentro da janela, sem tocar o banco."""
    tz = timezone_or_default(schedule.timezone)
    local_start = aware(window_start).astimezone(tz)
    local_end = aware(window_end).astimezone(tz)
    if schedule.schedule_type == "interval":
        return _interval_occurrences(schedule, local_start, local_end)
    if not schedule.cron_expression or not croniter.is_valid(schedule.cron_expression):
        return []
    occurrences: list[datetime] = []
    iterator = croniter(schedule.cron_expression, local_start - timedelta(seconds=1))
    for _ in range(MAX_OCCURRENCES_PER_SCHEDULE):
        occurs_at = iterator.get_next(datetime)
        if occurs_at > local_end:
            break
        occurrences.append(occurs_at)
        if schedule.is_one_time:
            break
    return occurrences


def _interval_occurrences(schedule: ScheduleDTO, window_start: datetime, window_end: datetime) -> list[datetime]:
    seconds = int(schedule.interval_seconds or 0)
    if seconds < 1:
        return []
    anchor = schedule.next_run_at or schedule.last_run_at or schedule.created_at
    if anchor is None:
        return []
    anchor = aware(anchor)
    step = timedelta(seconds=seconds)
    cursor = anchor
    guard = 0
    while cursor > window_start and guard < MAX_OCCURRENCES_PER_SCHEDULE * 4:
        cursor -= step
        guard += 1
    while cursor < window_start and guard < MAX_OCCURRENCES_PER_SCHEDULE * 4:
        cursor += step
        guard += 1
    occurrences: list[datetime] = []
    while cursor <= window_end and len(occurrences) < MAX_OCCURRENCES_PER_SCHEDULE:
        occurrences.append(cursor)
        cursor += step
    return occurrences


def classify_temporal_status(
    *,
    now: datetime,
    schedule_status: str,
    planned_start: datetime,
    misfire_grace_seconds: int,
    overlap_policy: str,
    record_status: str | None,
    record_started_at: datetime | None,
    record_reason: str | None,
    exec_status: str | None,
    has_conflicting_active_execution: bool,
) -> tuple[str, str | None]:
    """Classifica um item em passado/presente/futuro. Retorna (temporal_status, reason_label).

    Regra de atraso usa exclusivamente dados do servidor (misfire_grace_seconds do
    Schedule), nunca o relogio do navegador.
    """
    if record_status is None:
        if planned_start > now:
            if schedule_status in {"paused", "disabled"}:
                return "future_paused", "Agendamento pausado"
            if overlap_policy == "forbid" and has_conflicting_active_execution:
                return "future_overlap_risk", "Aguardando liberação"
            return "future_scheduled", None
        delay_seconds = (now - planned_start).total_seconds()
        if delay_seconds <= 90:
            return "awaiting_trigger", None
        if delay_seconds <= misfire_grace_seconds:
            return "delayed", None
        return "delayed", "Aguardando processamento do disparo"

    if record_status == "skipped":
        if record_reason == "overlap_forbid":
            return "past_skipped_overlap", "Ignorada por overlap"
        if record_reason == "misfire_skip":
            return "past_skipped_misfire", "Misfire ignorado"
        return "past_skipped_overlap", "Ignorada"

    if record_status == "failed" and record_started_at is None:
        return "past_dispatch_failed", "Falha ao disparar"

    effective = exec_status or record_status
    mapping = {
        "created": ("preparing", None),
        "pending": ("preparing", None),
        "running": ("running", None),
        "cancelling": ("cancelling", None),
        "succeeded": ("past_succeeded", None),
        "partially_succeeded": ("past_partial", None),
        "failed": ("past_failed", None),
        "cancelled": ("past_cancelled", None),
        "timed_out": ("past_timed_out", None),
    }
    return mapping.get(effective, ("past_unknown", None))


@dataclass(frozen=True)
class _Interval:
    key: int
    start: datetime
    end: datetime


def compute_overlap_groups(intervals: list[_Interval]) -> dict[int, tuple[int, int, int]]:
    """Agrupa intervalos que se sobrepoem em componentes conexos.

    Retorna {key: (overlap_group, overlap_index, overlap_count)}. Nao depende de
    pixels/coordenadas - o frontend decide o layout visual a partir do grupo.
    """
    normalized = [
        _Interval(key=iv.key, start=iv.start, end=max(iv.end, iv.start + timedelta(seconds=MIN_VISUAL_WIDTH_SECONDS)))
        for iv in intervals
    ]
    order = sorted(normalized, key=lambda iv: (iv.start, iv.end))
    groups: dict[int, tuple[int, int, int]] = {}
    group_id = 0
    i = 0
    n = len(order)
    while i < n:
        group_id += 1
        current_end = order[i].end
        members = [order[i]]
        j = i + 1
        while j < n and order[j].start < current_end:
            current_end = max(current_end, order[j].end)
            members.append(order[j])
            j += 1
        for idx, member in enumerate(members):
            groups[member.key] = (group_id, idx, len(members))
        i = j
    return groups


def bucketize_density(
    effective_starts: list[datetime],
    window_start: datetime,
    window_end: datetime,
    bucket_seconds: int,
) -> list[ScheduleCalendarDensityBucketDTO]:
    if bucket_seconds <= 0 or window_end <= window_start:
        return []
    bounds: list[tuple[datetime, datetime]] = []
    cursor = window_start
    while cursor < window_end:
        nxt = min(cursor + timedelta(seconds=bucket_seconds), window_end)
        bounds.append((cursor, nxt))
        cursor = nxt
    counts = [0] * len(bounds)
    for ts in effective_starts:
        for idx, (b_from, b_to) in enumerate(bounds):
            if b_from <= ts < b_to:
                counts[idx] += 1
                break
        else:
            if bounds and ts == bounds[-1][1]:
                counts[-1] += 1
    max_count = max(counts, default=0)
    result: list[ScheduleCalendarDensityBucketDTO] = []
    for (b_from, b_to), count in zip(bounds, counts):
        if count == 0 or max_count == 0:
            level = "none"
        elif count <= max(1, round(max_count * 0.34)):
            level = "low"
        elif count <= max(1, round(max_count * 0.67)):
            level = "medium"
        else:
            level = "high"
        result.append(ScheduleCalendarDensityBucketDTO(bucket_from=b_from, bucket_to=b_to, count=count, level=level))
    return result


def bucket_seconds_for_view(view: str) -> int:
    if view in {"day", "now"}:
        return 1800
    if view == "week":
        return 3600
    return 86400


def _status_matches(temporal_status: str, requested: str) -> bool:
    if temporal_status == requested:
        return True
    aliases = {
        "running": {"preparing", "running", "cancelling", "awaiting_trigger", "delayed"},
        "failed": {"past_failed", "past_timed_out", "past_dispatch_failed"},
        "completed": {"past_succeeded", "past_partial"},
        "succeeded": {"past_succeeded", "past_partial"},
        "future": None,
        "past": None,
    }
    if requested == "future":
        return temporal_status.startswith("future_")
    if requested == "past":
        return temporal_status.startswith("past_")
    return temporal_status in (aliases.get(requested) or set())


# --------------------------------------------------------------------------------------
# Orquestrador (I/O) - le Schedules, ScheduleExecutions, Executions e FlowExecutions reais.
# --------------------------------------------------------------------------------------


def build_schedule_calendar(
    db: Session,
    *,
    date_from: date,
    date_to: date,
    display_timezone: str = "America/Sao_Paulo",
    view: str = "month",
    target_type: str = "all",
    automation_ids: list[int] | None = None,
    flow_ids: list[str] | None = None,
    statuses: list[str] | None = None,
    owners: list[str] | None = None,
    search: str | None = None,
    now: datetime | None = None,
) -> ScheduleCalendarResultDTO:
    if date_to < date_from:
        raise CalendarQueryError("date_to deve ser maior ou igual a date_from.")
    if (date_to - date_from).days > MAX_RANGE_DAYS:
        raise CalendarQueryError(f"Intervalo maximo permitido e de {MAX_RANGE_DAYS} dias.")

    tz = timezone_or_default(display_timezone)
    window_start = datetime.combine(date_from, time.min, tzinfo=tz)
    window_end = datetime.combine(date_to, time.max, tzinfo=tz)
    current_time = aware(now) if now else datetime.now(UTC)

    schedules = _load_schedules(db, target_type=target_type, automation_ids=automation_ids, flow_ids=flow_ids, owners=owners)
    schedule_by_id = {s.id: s for s in schedules}

    if not schedules:
        return ScheduleCalendarResultDTO(
            range=ScheduleCalendarRangeDTO(date_from=window_start, date_to=window_end, timezone=display_timezone),
            items=[],
            summary=ScheduleCalendarSummaryDTO(total=0, completed=0, running=0, failed=0, future=0, cancelled=0, skipped=0, peak_from=None, peak_to=None, peak_count=0),
            density=bucketize_density([], window_start, window_end, bucket_seconds_for_view(view)),
        )

    schedule_ids = [s.id for s in schedules if s.id is not None]

    record_rows = db.scalars(
        select(ScheduleExecutionRecord).where(
            ScheduleExecutionRecord.schedule_id.in_(schedule_ids),
            ScheduleExecutionRecord.scheduled_for <= window_end,
            or_(
                ScheduleExecutionRecord.completed_at.is_(None),
                ScheduleExecutionRecord.completed_at >= window_start,
            ),
        )
    ).all()
    records_by_schedule: dict[int, list[ScheduleExecutionRecord]] = {}
    for row in record_rows:
        records_by_schedule.setdefault(row.schedule_id, []).append(row)

    active_earlier_by_schedule: dict[int, list[datetime]] = {}
    for schedule_id, rows in records_by_schedule.items():
        active_earlier_by_schedule[schedule_id] = [
            aware(r.scheduled_for) for r in rows if r.status in ACTIVE_SCHEDULE_EXECUTION_STATUSES
        ]

    execution_ids = {r.execution_id for r in record_rows if r.execution_id}
    flow_execution_ids = {r.flow_execution_id for r in record_rows if r.flow_execution_id}

    executions_by_id: dict[str, OrchestrationExecutionRecord] = {}
    if execution_ids:
        for row in db.scalars(select(OrchestrationExecutionRecord).where(OrchestrationExecutionRecord.id.in_(execution_ids))).all():
            executions_by_id[row.id] = row

    flow_executions_by_id: dict[str, FlowExecutionRecord] = {}
    if flow_execution_ids:
        for row in db.scalars(select(FlowExecutionRecord).where(FlowExecutionRecord.id.in_(flow_execution_ids))).all():
            flow_executions_by_id[row.id] = row

    progress_by_flow_execution = _load_flow_progress(db, flow_execution_ids)
    agent_by_execution = _load_agent_names(db, execution_ids)
    duration_estimates = _load_duration_estimates(db, schedules)
    target_names = _load_target_names(db, schedules)
    responsible_names = _load_responsible_names(db, {s.created_by for s in schedules if s.created_by})

    draft_items: list[ScheduleCalendarItemDTO] = []
    consumed_record_ids: set[str] = set()

    for schedule in schedules:
        if schedule.id is None:
            continue
        occurrence_times = occurrences_in_window(schedule, window_start, window_end)
        schedule_records = sorted(records_by_schedule.get(schedule.id, []), key=lambda r: r.scheduled_for)

        matched_ids: set[str] = set()
        for occurs_at in occurrence_times:
            record = _find_matching_record(occurs_at, schedule_records, matched_ids)
            if record is not None:
                matched_ids.add(record.id)
            draft_items.append(
                _build_item(
                    schedule=schedule,
                    planned_start=aware(occurs_at),
                    record=record,
                    now=current_time,
                    executions_by_id=executions_by_id,
                    flow_executions_by_id=flow_executions_by_id,
                    progress_by_flow_execution=progress_by_flow_execution,
                    agent_by_execution=agent_by_execution,
                    duration_estimates=duration_estimates,
                    target_names=target_names,
                    responsible_names=responsible_names,
                    active_earlier=active_earlier_by_schedule.get(schedule.id, []),
                )
            )
            consumed_record_ids.add(record.id) if record else None

        # ScheduleExecutions reais que nao bateram com nenhuma ocorrencia calculada
        # (ex.: disparo manual, drift de intervalo) ainda precisam aparecer.
        for record in schedule_records:
            if record.id in matched_ids:
                continue
            draft_items.append(
                _build_item(
                    schedule=schedule,
                    planned_start=aware(record.scheduled_for),
                    record=record,
                    now=current_time,
                    executions_by_id=executions_by_id,
                    flow_executions_by_id=flow_executions_by_id,
                    progress_by_flow_execution=progress_by_flow_execution,
                    agent_by_execution=agent_by_execution,
                    duration_estimates=duration_estimates,
                    target_names=target_names,
                    responsible_names=responsible_names,
                    active_earlier=active_earlier_by_schedule.get(schedule.id, []),
                )
            )

    filtered_items = _apply_post_filters(draft_items, statuses=statuses, search=search)

    intervals = [
        _Interval(key=idx, start=item.planned_start, end=item.effective_end or item.planned_start)
        for idx, item in enumerate(filtered_items)
    ]
    overlap_info = compute_overlap_groups(intervals)
    final_items: list[ScheduleCalendarItemDTO] = []
    for idx, item in enumerate(filtered_items):
        group, index, count = overlap_info.get(idx, (None, None, None))
        final_items.append(
            ScheduleCalendarItemDTO(
                **{**item.__dict__, "overlap_group": group, "overlap_index": index, "overlap_count": count}
            )
        )

    summary = _build_summary(final_items)
    density = bucketize_density(
        [item.planned_start for item in final_items],
        window_start,
        window_end,
        bucket_seconds_for_view(view),
    )

    return ScheduleCalendarResultDTO(
        range=ScheduleCalendarRangeDTO(date_from=window_start, date_to=window_end, timezone=display_timezone),
        items=final_items,
        summary=summary,
        density=density,
    )


def _find_matching_record(
    occurs_at: datetime,
    schedule_records: list[ScheduleExecutionRecord],
    already_matched: set[str],
) -> ScheduleExecutionRecord | None:
    occurs_aware = aware(occurs_at)
    for record in schedule_records:
        if record.id in already_matched:
            continue
        if abs((aware(record.scheduled_for) - occurs_aware).total_seconds()) <= 1:
            return record
    return None


def _build_item(
    *,
    schedule: ScheduleDTO,
    planned_start: datetime,
    record: ScheduleExecutionRecord | None,
    now: datetime,
    executions_by_id: dict[str, OrchestrationExecutionRecord],
    flow_executions_by_id: dict[str, FlowExecutionRecord],
    progress_by_flow_execution: dict[str, ScheduleCalendarProgressDTO],
    agent_by_execution: dict[str, str],
    duration_estimates: dict[tuple[str, str], tuple[float, str, int]],
    target_names: dict[tuple[str, str], tuple[str, str | None]],
    responsible_names: dict[str, str],
    active_earlier: list[datetime],
) -> ScheduleCalendarItemDTO:
    execution = executions_by_id.get(record.execution_id) if record and record.execution_id else None
    flow_execution = flow_executions_by_id.get(record.flow_execution_id) if record and record.flow_execution_id else None

    actual_start = (execution.started_at if execution else None) or (flow_execution.started_at if flow_execution else None)
    actual_end = (execution.completed_at if execution else None) or (flow_execution.completed_at if flow_execution else None)
    exec_status = (flow_execution.status if flow_execution else None) or (execution.status if execution else None)
    record_reason = None
    if record and isinstance(record.result, dict):
        record_reason = record.result.get("reason")

    has_conflict = any(t < planned_start for t in active_earlier)

    temporal_status, reason = classify_temporal_status(
        now=now,
        schedule_status=schedule.status,
        planned_start=planned_start,
        misfire_grace_seconds=schedule.misfire_grace_seconds,
        overlap_policy=schedule.overlap_policy,
        record_status=record.status if record else None,
        record_started_at=record.started_at if record else None,
        record_reason=record_reason,
        exec_status=exec_status,
        has_conflicting_active_execution=has_conflict,
    )

    target_key = (
        ("automation", str(schedule.automation_version_id or schedule.automation_id))
        if schedule.target_type == "automation"
        else ("flow", str(schedule.flow_version_id))
    )
    target_name, target_version = target_names.get(target_key, (schedule.name or "—", None))

    estimate_key = (
        ("automation_version", str(schedule.automation_version_id))
        if schedule.automation_version_id
        else ("automation", str(schedule.automation_id))
        if schedule.automation_id
        else ("flow_version", str(schedule.flow_version_id))
    )
    estimated_duration_seconds: float | None = None
    estimation_confidence: str | None = None
    if estimate_key in duration_estimates:
        estimated_duration_seconds, estimation_confidence, _ = duration_estimates[estimate_key]

    duration_seconds = None
    if actual_start and actual_end:
        duration_seconds = (aware(actual_end) - aware(actual_start)).total_seconds()

    is_estimated = duration_seconds is None and estimated_duration_seconds is not None
    effective_end = None
    if actual_end:
        effective_end = aware(actual_end)
    elif is_estimated and temporal_status in {"running", "preparing", "cancelling", "future_scheduled", "future_overlap_risk", "delayed", "awaiting_trigger"}:
        base = aware(actual_start) if actual_start else planned_start
        effective_end = base + timedelta(seconds=estimated_duration_seconds)

    progress = progress_by_flow_execution.get(record.flow_execution_id) if record and record.flow_execution_id else None

    agent_name = agent_by_execution.get(record.execution_id) if record and record.execution_id else None

    item_id = record.id if record else f"virtual:{schedule.id}:{planned_start.isoformat()}"

    return ScheduleCalendarItemDTO(
        id=item_id,
        schedule_id=int(schedule.id),
        schedule_execution_id=record.id if record else None,
        execution_id=record.execution_id if record else None,
        flow_execution_id=record.flow_execution_id if record else None,
        target_type=schedule.target_type,
        target_id=str(schedule.automation_id or schedule.automation_version_id or schedule.flow_id or schedule.flow_version_id or ""),
        target_version=target_version,
        target_name=target_name,
        schedule_name=schedule.name,
        planned_start=planned_start,
        actual_start=aware(actual_start) if actual_start else None,
        actual_end=aware(actual_end) if actual_end else None,
        effective_end=effective_end,
        status=exec_status or (record.status if record else "planned"),
        temporal_status=temporal_status,
        reason=reason,
        progress=progress,
        responsible=responsible_names.get(schedule.created_by or "", schedule.created_by),
        agent=agent_name,
        duration_seconds=duration_seconds,
        estimated_duration_seconds=estimated_duration_seconds,
        estimation_confidence=estimation_confidence,
        is_estimated=is_estimated,
        recurrence_type=schedule.recurrence_type,
        schedule_type=schedule.schedule_type,
        timezone=schedule.timezone,
        is_one_time=schedule.is_one_time,
    )


def _apply_post_filters(
    items: list[ScheduleCalendarItemDTO],
    *,
    statuses: list[str] | None,
    search: str | None,
) -> list[ScheduleCalendarItemDTO]:
    result = items
    if statuses:
        result = [item for item in result if any(_status_matches(item.temporal_status, s) for s in statuses)]
    if search:
        term = search.strip().lower()
        if term:
            result = [
                item
                for item in result
                if term in (item.schedule_name or "").lower()
                or term in (item.target_name or "").lower()
                or term in (item.responsible or "").lower()
                or term in str(item.schedule_id)
                or term in (item.target_id or "").lower()
            ]
    return result


def _build_summary(items: list[ScheduleCalendarItemDTO]) -> ScheduleCalendarSummaryDTO:
    completed = sum(1 for i in items if i.temporal_status in {"past_succeeded", "past_partial"})
    running = sum(1 for i in items if i.temporal_status in {"preparing", "running", "cancelling", "awaiting_trigger", "delayed"})
    failed = sum(1 for i in items if i.temporal_status in {"past_failed", "past_timed_out", "past_dispatch_failed"})
    future = sum(1 for i in items if i.temporal_status.startswith("future_"))
    cancelled = sum(1 for i in items if i.temporal_status == "past_cancelled")
    skipped = sum(1 for i in items if i.temporal_status in {"past_skipped_overlap", "past_skipped_misfire"})

    peak_from = peak_to = None
    peak_count = 0
    groups: dict[int, list[ScheduleCalendarItemDTO]] = {}
    for item in items:
        if item.overlap_group is not None and (item.overlap_count or 0) > 1:
            groups.setdefault(item.overlap_group, []).append(item)
    if groups:
        biggest = max(groups.values(), key=len)
        peak_count = len(biggest)
        peak_from = min(i.planned_start for i in biggest)
        ends = [i.effective_end or i.planned_start for i in biggest]
        peak_to = max(ends)

    return ScheduleCalendarSummaryDTO(
        total=len(items),
        completed=completed,
        running=running,
        failed=failed,
        future=future,
        cancelled=cancelled,
        skipped=skipped,
        peak_from=peak_from,
        peak_to=peak_to,
        peak_count=peak_count,
    )


# --------------------------------------------------------------------------------------
# Carregamento em lote (evita N+1).
# --------------------------------------------------------------------------------------


def _load_schedules(
    db: Session,
    *,
    target_type: str,
    automation_ids: list[int] | None,
    flow_ids: list[str] | None,
    owners: list[str] | None,
) -> list[ScheduleDTO]:
    from modules.orchestration.scheduling.infrastructure.repositories.sqlalchemy_scheduling import _schedule_to_dto

    query = select(Schedule)
    if target_type in {"automation", "flow"}:
        query = query.where(Schedule.target_type == target_type)
    if automation_ids:
        version_ids = db.scalars(
            select(CatalogAutomationVersionRecord.id).where(CatalogAutomationVersionRecord.automation_id.in_(automation_ids))
        ).all()
        query = query.where(
            or_(
                Schedule.automation_id.in_(automation_ids),
                Schedule.automation_version_id.in_(version_ids) if version_ids else False,
            )
        )
    if flow_ids:
        flow_version_ids = db.scalars(select(FlowVersionRecord.id).where(FlowVersionRecord.flow_id.in_(flow_ids))).all()
        query = query.where(
            or_(
                Schedule.flow_id.in_(flow_ids),
                Schedule.flow_version_id.in_(flow_version_ids) if flow_version_ids else False,
            )
        )
    if owners:
        query = query.where(Schedule.created_by.in_(owners))
    query = query.where(Schedule.archived_at.is_(None)).order_by(Schedule.id.asc()).limit(MAX_SCHEDULES)
    rows = db.scalars(query).all()
    return [_schedule_to_dto(row) for row in rows]


def _load_flow_progress(db: Session, flow_execution_ids: set[str]) -> dict[str, ScheduleCalendarProgressDTO]:
    if not flow_execution_ids:
        return {}
    rows = db.execute(
        select(FlowNodeExecutionRecord.flow_execution_id, FlowNodeExecutionRecord.status, func.count())
        .where(FlowNodeExecutionRecord.flow_execution_id.in_(flow_execution_ids))
        .group_by(FlowNodeExecutionRecord.flow_execution_id, FlowNodeExecutionRecord.status)
    ).all()
    buckets: dict[str, dict[str, int]] = {}
    for flow_execution_id, status, count in rows:
        buckets.setdefault(flow_execution_id, {})[status] = count
    result: dict[str, ScheduleCalendarProgressDTO] = {}
    for flow_execution_id, counts in buckets.items():
        succeeded = counts.get("succeeded", 0) + counts.get("skipped", 0)
        running = counts.get("running", 0)
        failed = counts.get("failed", 0) + counts.get("timed_out", 0) + counts.get("cancelled", 0)
        total = sum(counts.values())
        pending = max(total - succeeded - running - failed, 0)
        result[flow_execution_id] = ScheduleCalendarProgressDTO(total=total, succeeded=succeeded, running=running, failed=failed, pending=pending)
    return result


def _load_agent_names(db: Session, execution_ids: set[str]) -> dict[str, str]:
    if not execution_ids:
        return {}
    rows = db.execute(
        select(TaskExecutionRecord.execution_id, AgentRecord.name, ExecutionAttemptRecord.created_at)
        .join(ExecutionAttemptRecord, ExecutionAttemptRecord.task_execution_id == TaskExecutionRecord.id)
        .join(AgentRecord, AgentRecord.id == ExecutionAttemptRecord.agent_id)
        .where(TaskExecutionRecord.execution_id.in_(execution_ids))
        .order_by(TaskExecutionRecord.execution_id, ExecutionAttemptRecord.created_at.desc())
    ).all()
    result: dict[str, str] = {}
    for execution_id, agent_name, _created_at in rows:
        result.setdefault(execution_id, agent_name)
    return result


def _load_duration_estimates(db: Session, schedules: list[ScheduleDTO]) -> dict[tuple[str, str], tuple[float, str, int]]:
    automation_version_ids = sorted({str(s.automation_version_id) for s in schedules if s.automation_version_id})
    automation_ids_only = sorted({str(s.automation_id) for s in schedules if s.automation_id and not s.automation_version_id})
    flow_version_ids = sorted({s.flow_version_id for s in schedules if s.flow_version_id})

    result: dict[tuple[str, str], tuple[float, str, int]] = {}

    if automation_version_ids:
        version_ids_int = [int(v) for v in automation_version_ids]
        subq = (
            select(
                TaskExecutionRecord.automation_version_id.label("key"),
                OrchestrationExecutionRecord.started_at.label("started_at"),
                OrchestrationExecutionRecord.completed_at.label("completed_at"),
                func.row_number()
                .over(partition_by=TaskExecutionRecord.automation_version_id, order_by=OrchestrationExecutionRecord.completed_at.desc())
                .label("rn"),
            )
            .join(OrchestrationExecutionRecord, OrchestrationExecutionRecord.id == TaskExecutionRecord.execution_id)
            .where(
                TaskExecutionRecord.automation_version_id.in_(version_ids_int),
                OrchestrationExecutionRecord.status.in_(("succeeded", "partially_succeeded")),
                OrchestrationExecutionRecord.started_at.is_not(None),
                OrchestrationExecutionRecord.completed_at.is_not(None),
            )
        ).subquery()
        rows = db.execute(
            select(subq.c.key, func.avg(func.extract("epoch", subq.c.completed_at - subq.c.started_at)), func.count())
            .where(subq.c.rn <= DURATION_HISTORY_SAMPLE)
            .group_by(subq.c.key)
        ).all()
        for key, avg_seconds, count in rows:
            if avg_seconds is None:
                continue
            result[("automation_version", str(key))] = (float(avg_seconds), _confidence(count), int(count))

    if automation_ids_only:
        ids_int = [int(v) for v in automation_ids_only]
        subq = (
            select(
                CatalogAutomationVersionRecord.automation_id.label("key"),
                OrchestrationExecutionRecord.started_at.label("started_at"),
                OrchestrationExecutionRecord.completed_at.label("completed_at"),
                func.row_number()
                .over(partition_by=CatalogAutomationVersionRecord.automation_id, order_by=OrchestrationExecutionRecord.completed_at.desc())
                .label("rn"),
            )
            .select_from(TaskExecutionRecord)
            .join(OrchestrationExecutionRecord, OrchestrationExecutionRecord.id == TaskExecutionRecord.execution_id)
            .join(CatalogAutomationVersionRecord, CatalogAutomationVersionRecord.id == TaskExecutionRecord.automation_version_id)
            .where(
                CatalogAutomationVersionRecord.automation_id.in_(ids_int),
                OrchestrationExecutionRecord.status.in_(("succeeded", "partially_succeeded")),
                OrchestrationExecutionRecord.started_at.is_not(None),
                OrchestrationExecutionRecord.completed_at.is_not(None),
            )
        ).subquery()
        rows = db.execute(
            select(subq.c.key, func.avg(func.extract("epoch", subq.c.completed_at - subq.c.started_at)), func.count())
            .where(subq.c.rn <= DURATION_HISTORY_SAMPLE)
            .group_by(subq.c.key)
        ).all()
        for key, avg_seconds, count in rows:
            if avg_seconds is None:
                continue
            result[("automation", str(key))] = (float(avg_seconds), _confidence(count), int(count))

    if flow_version_ids:
        subq = (
            select(
                FlowExecutionRecord.flow_version_id.label("key"),
                FlowExecutionRecord.started_at.label("started_at"),
                FlowExecutionRecord.completed_at.label("completed_at"),
                func.row_number()
                .over(partition_by=FlowExecutionRecord.flow_version_id, order_by=FlowExecutionRecord.completed_at.desc())
                .label("rn"),
            )
            .where(
                FlowExecutionRecord.flow_version_id.in_(flow_version_ids),
                FlowExecutionRecord.status.in_(("succeeded", "partially_succeeded")),
                FlowExecutionRecord.started_at.is_not(None),
                FlowExecutionRecord.completed_at.is_not(None),
            )
        ).subquery()
        rows = db.execute(
            select(subq.c.key, func.avg(func.extract("epoch", subq.c.completed_at - subq.c.started_at)), func.count())
            .where(subq.c.rn <= DURATION_HISTORY_SAMPLE)
            .group_by(subq.c.key)
        ).all()
        for key, avg_seconds, count in rows:
            if avg_seconds is None:
                continue
            result[("flow_version", str(key))] = (float(avg_seconds), _confidence(count), int(count))

    return result


def _confidence(count: int) -> str:
    if count >= 8:
        return "high"
    if count >= 3:
        return "medium"
    return "low"


def _load_target_names(db: Session, schedules: list[ScheduleDTO]) -> dict[tuple[str, str], tuple[str, str | None]]:
    result: dict[tuple[str, str], tuple[str, str | None]] = {}

    automation_version_ids = {int(s.automation_version_id) for s in schedules if s.automation_version_id}
    version_to_automation: dict[int, tuple[int, str]] = {}
    if automation_version_ids:
        for row in db.execute(
            select(CatalogAutomationVersionRecord.id, CatalogAutomationVersionRecord.automation_id, CatalogAutomationVersionRecord.version).where(
                CatalogAutomationVersionRecord.id.in_(automation_version_ids)
            )
        ).all():
            version_to_automation[row.id] = (row.automation_id, row.version)

    automation_ids = {int(s.automation_id) for s in schedules if s.automation_id}
    automation_ids |= {aid for aid, _ in version_to_automation.values()}
    automation_names: dict[int, str] = {}
    if automation_ids:
        for row in db.execute(select(CatalogAutomationRecord.id, CatalogAutomationRecord.name).where(CatalogAutomationRecord.id.in_(automation_ids))).all():
            automation_names[row.id] = row.name

    for schedule in schedules:
        if schedule.target_type != "automation":
            continue
        version = None
        automation_id = schedule.automation_id
        if schedule.automation_version_id and int(schedule.automation_version_id) in version_to_automation:
            automation_id, version = version_to_automation[int(schedule.automation_version_id)]
        key = ("automation", str(schedule.automation_version_id or schedule.automation_id))
        name = automation_names.get(automation_id, schedule.name or "Automação")
        result[key] = (name, version)

    flow_version_ids = {s.flow_version_id for s in schedules if s.flow_version_id}
    version_to_flow: dict[str, tuple[str, str]] = {}
    if flow_version_ids:
        for row in db.execute(
            select(FlowVersionRecord.id, FlowVersionRecord.flow_id, FlowVersionRecord.version).where(FlowVersionRecord.id.in_(flow_version_ids))
        ).all():
            version_to_flow[row.id] = (row.flow_id, row.version)

    flow_ids = {s.flow_id for s in schedules if s.flow_id}
    flow_ids |= {fid for fid, _ in version_to_flow.values()}
    flow_names: dict[str, str] = {}
    if flow_ids:
        for row in db.execute(select(FlowRecord.id, FlowRecord.name).where(FlowRecord.id.in_(flow_ids))).all():
            flow_names[row.id] = row.name

    for schedule in schedules:
        if schedule.target_type != "flow":
            continue
        flow_id = schedule.flow_id
        version = None
        if schedule.flow_version_id and schedule.flow_version_id in version_to_flow:
            flow_id, version = version_to_flow[schedule.flow_version_id]
        key = ("flow", str(schedule.flow_version_id))
        name = flow_names.get(flow_id, schedule.name or "Fluxo")
        result[key] = (name, version)

    return result


def _load_responsible_names(db: Session, created_by_values: set[str]) -> dict[str, str]:
    int_ids: dict[int, str] = {}
    for value in created_by_values:
        try:
            int_ids[int(value)] = value
        except (TypeError, ValueError):
            continue
    if not int_ids:
        return {}
    result: dict[str, str] = {}
    for row in db.execute(select(AccessUserRecord.id, AccessUserRecord.name).where(AccessUserRecord.id.in_(int_ids.keys()))).all():
        original = int_ids.get(row.id)
        if original:
            result[original] = row.name
    return result
