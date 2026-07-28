from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from croniter import croniter


DEFAULT_TIMEZONE = "America/Sao_Paulo"
RECURRENCE_TYPES = {"daily", "weekly", "monthly", "once"}


class RecurrenceError(ValueError):
    pass


@dataclass(frozen=True)
class RecurrenceInput:
    recurrence_type: str
    time_of_day: str
    weekdays: list[int] | None = None
    day_of_month: int | None = None
    specific_date: date | None = None


def build_cron_expression(data: RecurrenceInput) -> str:
    if data.recurrence_type not in RECURRENCE_TYPES:
        raise RecurrenceError(f"recurrence_type invalido: {data.recurrence_type!r}")
    hour, minute = parse_time_of_day(data.time_of_day)
    if data.recurrence_type == "daily":
        return f"{minute} {hour} * * *"
    if data.recurrence_type == "weekly":
        if not data.weekdays:
            raise RecurrenceError("Selecione ao menos um dia da semana.")
        for day in data.weekdays:
            if not (0 <= day <= 6):
                raise RecurrenceError(f"Dia da semana invalido: {day!r}")
        cron_days = sorted({(day + 1) % 7 for day in data.weekdays})
        return f"{minute} {hour} * * {','.join(str(day) for day in cron_days)}"
    if data.recurrence_type == "monthly":
        if data.day_of_month is None:
            raise RecurrenceError("Selecione o dia do mes.")
        if data.day_of_month == 0:
            return f"{minute} {hour} 28 * *"
        if not (1 <= data.day_of_month <= 31):
            raise RecurrenceError(f"Dia do mes invalido: {data.day_of_month!r}")
        return f"{minute} {hour} {data.day_of_month} * *"
    if data.specific_date is None:
        raise RecurrenceError("Selecione a data.")
    return f"{minute} {hour} {data.specific_date.day} {data.specific_date.month} *"


def calculate_next_run(
    *,
    schedule_type: str,
    cron_expression: str | None,
    timezone: str,
    after: datetime,
    recurrence_type: str | None = None,
    time_of_day: str | None = None,
    specific_date: date | None = None,
    interval_seconds: int | None = None,
) -> datetime | None:
    tz = timezone_or_default(timezone)
    base = aware(after).astimezone(tz)
    if schedule_type == "once" or recurrence_type == "once":
        if specific_date is None:
            return None
        hour, minute = parse_time_of_day(time_of_day or "00:00")
        run_at = datetime.combine(specific_date, time(hour=hour, minute=minute), tzinfo=tz)
        return run_at if run_at > base else None
    if schedule_type == "interval":
        seconds = int(interval_seconds or 0)
        if seconds < 60:
            raise RecurrenceError("Intervalo minimo e de 60 segundos.")
        return base + timedelta(seconds=seconds)
    if not cron_expression:
        raise RecurrenceError("cron_expression e obrigatorio para Schedule cron.")
    if not croniter.is_valid(cron_expression):
        raise RecurrenceError("cron_expression invalido.")
    return croniter(cron_expression, base).get_next(datetime)


def parse_time_of_day(time_of_day: str) -> tuple[int, int]:
    try:
        hour_str, minute_str = time_of_day.strip().split(":", 1)
        hour, minute = int(hour_str), int(minute_str)
    except (ValueError, AttributeError) as exc:
        raise RecurrenceError(f"Horario invalido: {time_of_day!r} (use HH:MM)") from exc
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise RecurrenceError(f"Horario fora do intervalo: {time_of_day!r}")
    return hour, minute


def timezone_or_default(timezone: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(timezone or DEFAULT_TIMEZONE)
    except Exception:
        return ZoneInfo(DEFAULT_TIMEZONE)


def aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
