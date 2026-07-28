from __future__ import annotations

from datetime import datetime

import pytest

from modules.orchestration.scheduling.domain import RecurrenceError, RecurrenceInput, build_cron_expression, calculate_next_run


def test_build_weekly_cron_converts_iso_weekdays_to_cron_weekdays() -> None:
    assert build_cron_expression(RecurrenceInput(recurrence_type="weekly", time_of_day="08:30", weekdays=[0, 6])) == "30 8 * * 0,1"


def test_once_schedule_returns_none_after_planned_time() -> None:
    next_run = calculate_next_run(
        schedule_type="once",
        cron_expression=None,
        timezone="America/Sao_Paulo",
        after=datetime(2026, 7, 28, 12, 0),
        recurrence_type="once",
        time_of_day="08:00",
        specific_date=datetime(2026, 7, 28).date(),
    )

    assert next_run is None


def test_interval_schedule_enforces_minimum_frequency() -> None:
    with pytest.raises(RecurrenceError):
        calculate_next_run(
            schedule_type="interval",
            cron_expression=None,
            timezone="UTC",
            after=datetime(2026, 7, 28, 12, 0),
            interval_seconds=30,
        )


def test_interval_schedule_calculates_from_planned_base() -> None:
    base = datetime(2026, 7, 28, 12, 0)
    next_run = calculate_next_run(
        schedule_type="interval",
        cron_expression=None,
        timezone="UTC",
        after=base,
        interval_seconds=900,
    )

    assert next_run.replace(tzinfo=None) == datetime(2026, 7, 28, 12, 15)
