"""
Turns the structured recurrence choices from the schedule picker (frequency +
time-of-day + weekdays/day-of-month/specific-date) into a cron expression --
the cron expression stays the single source of truth actually used for
dispatch (sync_schedules) and calendar math (via croniter), the structured
fields exist purely so the UI never has to parse cron back into human terms.

No DB dependency, unit-testable in isolation (mirrors app/domain/automation_manifest.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

RECURRENCE_TYPES = {"daily", "weekly", "monthly", "once"}


class RecurrenceError(ValueError):
    pass


@dataclass
class RecurrenceInput:
    recurrence_type: str
    time_of_day: str  # "HH:MM"
    weekdays: list[int] | None = None  # 0=Mon .. 6=Sun, for "weekly"
    day_of_month: int | None = None  # 1-31, or 0 for "last day", for "monthly"
    specific_date: date | None = None  # for "once"


def _parse_time_of_day(time_of_day: str) -> tuple[int, int]:
    try:
        hour_str, minute_str = time_of_day.strip().split(":", 1)
        hour, minute = int(hour_str), int(minute_str)
    except (ValueError, AttributeError) as exc:
        raise RecurrenceError(f"Horário inválido: {time_of_day!r} (use HH:MM)") from exc
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise RecurrenceError(f"Horário fora do intervalo: {time_of_day!r}")
    return hour, minute


def build_cron_expression(data: RecurrenceInput) -> str:
    if data.recurrence_type not in RECURRENCE_TYPES:
        raise RecurrenceError(f"recurrence_type inválido: {data.recurrence_type!r}")
    hour, minute = _parse_time_of_day(data.time_of_day)

    if data.recurrence_type == "daily":
        return f"{minute} {hour} * * *"

    if data.recurrence_type == "weekly":
        if not data.weekdays:
            raise RecurrenceError("Selecione ao menos um dia da semana.")
        for day in data.weekdays:
            if not (0 <= day <= 6):
                raise RecurrenceError(f"Dia da semana inválido: {day!r} (use 0=segunda .. 6=domingo)")
        # cron weekday numbering: 0=Sunday .. 6=Saturday. Our input uses
        # 0=Monday .. 6=Sunday (ISO-ish, matches how the picker presents
        # Seg..Dom left to right) -- convert.
        cron_days = sorted({(day + 1) % 7 for day in data.weekdays})
        return f"{minute} {hour} * * {','.join(str(d) for d in cron_days)}"

    if data.recurrence_type == "monthly":
        if data.day_of_month is None:
            raise RecurrenceError("Selecione o dia do mês.")
        if data.day_of_month == 0:
            # "last day of the month" has no single cron representation across
            # every month -- approximate with day 28 and let the dispatcher's
            # explicit last-day check (see schedule_tasks.py) handle it, OR
            # simplify for now: run on the 28th, which exists in every month.
            # Flagged for a future refinement (true "last day" support).
            return f"{minute} {hour} 28 * *"
        if not (1 <= data.day_of_month <= 31):
            raise RecurrenceError(f"Dia do mês inválido: {data.day_of_month!r}")
        return f"{minute} {hour} {data.day_of_month} * *"

    if data.recurrence_type == "once":
        if data.specific_date is None:
            raise RecurrenceError("Selecione a data.")
        d = data.specific_date
        return f"{minute} {hour} {d.day} {d.month} *"

    raise RecurrenceError(f"recurrence_type não implementado: {data.recurrence_type!r}")
