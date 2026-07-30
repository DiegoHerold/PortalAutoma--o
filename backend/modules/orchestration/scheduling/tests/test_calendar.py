from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from modules.orchestration.scheduling.application.calendar import (
    _Interval,
    bucketize_density,
    classify_temporal_status,
    compute_overlap_groups,
    occurrences_in_window,
)
from modules.orchestration.scheduling.application.dto import ScheduleDTO

SP = ZoneInfo("America/Sao_Paulo")


def _schedule(**overrides) -> ScheduleDTO:
    base = dict(
        id=1,
        key="sch_1",
        name="Fechamento mensal",
        automation_id=10,
        automation_version_id=None,
        flow_id=None,
        flow_version_id=None,
        target_type="automation",
        cron_expression="0 8 * * *",
        timezone="America/Sao_Paulo",
        is_active=True,
        status="active",
        schedule_type="cron",
        recurrence_type="daily",
        time_of_day="08:00",
        weekdays=None,
        day_of_month=None,
        specific_date=None,
        interval_seconds=None,
        is_one_time=False,
        payload={},
        misfire_policy="run_once_now",
        max_catch_up_runs=1,
        misfire_grace_seconds=3600,
        overlap_policy="forbid",
        next_run_at=None,
        last_run_at=None,
        last_dispatched_at=None,
        created_by="1",
    )
    base.update(overrides)
    return ScheduleDTO(**base)


class TestOccurrencesInWindow:
    def test_daily_cron_returns_one_occurrence_per_day(self) -> None:
        schedule = _schedule()
        window_start = datetime(2026, 7, 27, 0, 0, tzinfo=SP)
        window_end = datetime(2026, 7, 29, 23, 59, 59, tzinfo=SP)

        occurrences = occurrences_in_window(schedule, window_start, window_end)

        assert len(occurrences) == 3
        assert all(o.hour == 8 and o.minute == 0 for o in occurrences)

    def test_once_schedule_stops_after_first_occurrence(self) -> None:
        schedule = _schedule(schedule_type="cron", recurrence_type="once", is_one_time=True, cron_expression="0 8 29 7 *")
        window_start = datetime(2026, 7, 1, 0, 0, tzinfo=SP)
        window_end = datetime(2026, 12, 31, 23, 59, tzinfo=SP)

        occurrences = occurrences_in_window(schedule, window_start, window_end)

        assert len(occurrences) == 1

    def test_interval_schedule_generates_occurrences_at_fixed_step(self) -> None:
        anchor = datetime(2026, 7, 29, 9, 0, tzinfo=UTC)
        schedule = _schedule(schedule_type="interval", cron_expression=None, interval_seconds=3600, next_run_at=anchor)
        window_start = datetime(2026, 7, 29, 6, 0, tzinfo=UTC)
        window_end = datetime(2026, 7, 29, 12, 0, tzinfo=UTC)

        occurrences = occurrences_in_window(schedule, window_start, window_end)

        assert len(occurrences) == 7  # 06:00, 07:00, ..., 12:00
        deltas = {(b - a).total_seconds() for a, b in zip(occurrences, occurrences[1:])}
        assert deltas == {3600.0}

    def test_interval_schedule_without_anchor_returns_empty(self) -> None:
        schedule = _schedule(schedule_type="interval", cron_expression=None, interval_seconds=3600, next_run_at=None, last_run_at=None)
        occurrences = occurrences_in_window(schedule, datetime(2026, 7, 29, tzinfo=UTC), datetime(2026, 7, 30, tzinfo=UTC))
        assert occurrences == []


class TestClassifyTemporalStatus:
    def test_future_occurrence_without_record_is_scheduled(self) -> None:
        now = datetime(2026, 7, 29, 7, 0, tzinfo=UTC)
        status, reason = classify_temporal_status(
            now=now,
            schedule_status="active",
            planned_start=datetime(2026, 7, 29, 9, 0, tzinfo=UTC),
            misfire_grace_seconds=3600,
            overlap_policy="forbid",
            record_status=None,
            record_started_at=None,
            record_reason=None,
            exec_status=None,
            has_conflicting_active_execution=False,
        )
        assert status == "future_scheduled"
        assert reason is None

    def test_future_occurrence_of_paused_schedule(self) -> None:
        now = datetime(2026, 7, 29, 7, 0, tzinfo=UTC)
        status, reason = classify_temporal_status(
            now=now,
            schedule_status="paused",
            planned_start=datetime(2026, 7, 29, 9, 0, tzinfo=UTC),
            misfire_grace_seconds=3600,
            overlap_policy="forbid",
            record_status=None,
            record_started_at=None,
            record_reason=None,
            exec_status=None,
            has_conflicting_active_execution=False,
        )
        assert status == "future_paused"
        assert reason == "Agendamento pausado"

    def test_future_overlap_risk_when_earlier_active_execution_exists(self) -> None:
        now = datetime(2026, 7, 29, 7, 0, tzinfo=UTC)
        status, reason = classify_temporal_status(
            now=now,
            schedule_status="active",
            planned_start=datetime(2026, 7, 29, 9, 0, tzinfo=UTC),
            misfire_grace_seconds=3600,
            overlap_policy="forbid",
            record_status=None,
            record_started_at=None,
            record_reason=None,
            exec_status=None,
            has_conflicting_active_execution=True,
        )
        assert status == "future_overlap_risk"

    def test_awaiting_trigger_within_short_tolerance(self) -> None:
        now = datetime(2026, 7, 29, 9, 1, tzinfo=UTC)
        status, _ = classify_temporal_status(
            now=now,
            schedule_status="active",
            planned_start=datetime(2026, 7, 29, 9, 0, tzinfo=UTC),
            misfire_grace_seconds=3600,
            overlap_policy="forbid",
            record_status=None,
            record_started_at=None,
            record_reason=None,
            exec_status=None,
            has_conflicting_active_execution=False,
        )
        assert status == "awaiting_trigger"

    def test_delayed_beyond_tolerance_but_within_grace(self) -> None:
        now = datetime(2026, 7, 29, 9, 10, tzinfo=UTC)
        status, _ = classify_temporal_status(
            now=now,
            schedule_status="active",
            planned_start=datetime(2026, 7, 29, 9, 0, tzinfo=UTC),
            misfire_grace_seconds=3600,
            overlap_policy="forbid",
            record_status=None,
            record_started_at=None,
            record_reason=None,
            exec_status=None,
            has_conflicting_active_execution=False,
        )
        assert status == "delayed"

    def test_past_skipped_overlap(self) -> None:
        status, reason = classify_temporal_status(
            now=datetime(2026, 7, 29, 10, 0, tzinfo=UTC),
            schedule_status="active",
            planned_start=datetime(2026, 7, 29, 9, 0, tzinfo=UTC),
            misfire_grace_seconds=3600,
            overlap_policy="forbid",
            record_status="skipped",
            record_started_at=None,
            record_reason="overlap_forbid",
            exec_status=None,
            has_conflicting_active_execution=False,
        )
        assert status == "past_skipped_overlap"
        assert reason == "Ignorada por overlap"

    def test_past_dispatch_failed_when_never_started(self) -> None:
        status, reason = classify_temporal_status(
            now=datetime(2026, 7, 29, 10, 0, tzinfo=UTC),
            schedule_status="active",
            planned_start=datetime(2026, 7, 29, 9, 0, tzinfo=UTC),
            misfire_grace_seconds=3600,
            overlap_policy="forbid",
            record_status="failed",
            record_started_at=None,
            record_reason=None,
            exec_status=None,
            has_conflicting_active_execution=False,
        )
        assert status == "past_dispatch_failed"
        assert reason == "Falha ao disparar"

    def test_running_execution(self) -> None:
        status, _ = classify_temporal_status(
            now=datetime(2026, 7, 29, 9, 5, tzinfo=UTC),
            schedule_status="active",
            planned_start=datetime(2026, 7, 29, 9, 0, tzinfo=UTC),
            misfire_grace_seconds=3600,
            overlap_policy="forbid",
            record_status="running",
            record_started_at=datetime(2026, 7, 29, 9, 2, tzinfo=UTC),
            record_reason=None,
            exec_status="running",
            has_conflicting_active_execution=False,
        )
        assert status == "running"

    def test_succeeded_execution(self) -> None:
        status, _ = classify_temporal_status(
            now=datetime(2026, 7, 29, 10, 0, tzinfo=UTC),
            schedule_status="active",
            planned_start=datetime(2026, 7, 29, 9, 0, tzinfo=UTC),
            misfire_grace_seconds=3600,
            overlap_policy="forbid",
            record_status="succeeded",
            record_started_at=datetime(2026, 7, 29, 9, 2, tzinfo=UTC),
            record_reason=None,
            exec_status="succeeded",
            has_conflicting_active_execution=False,
        )
        assert status == "past_succeeded"


class TestOverlapGroups:
    def test_non_overlapping_intervals_get_distinct_groups(self) -> None:
        intervals = [
            _Interval(key=0, start=datetime(2026, 7, 29, 8, 0, tzinfo=UTC), end=datetime(2026, 7, 29, 8, 30, tzinfo=UTC)),
            _Interval(key=1, start=datetime(2026, 7, 29, 10, 0, tzinfo=UTC), end=datetime(2026, 7, 29, 10, 30, tzinfo=UTC)),
        ]
        groups = compute_overlap_groups(intervals)
        assert groups[0][0] != groups[1][0]
        assert groups[0] == (groups[0][0], 0, 1)

    def test_overlapping_intervals_share_group_with_correct_count(self) -> None:
        intervals = [
            _Interval(key=0, start=datetime(2026, 7, 29, 8, 0, tzinfo=UTC), end=datetime(2026, 7, 29, 9, 0, tzinfo=UTC)),
            _Interval(key=1, start=datetime(2026, 7, 29, 8, 30, tzinfo=UTC), end=datetime(2026, 7, 29, 9, 30, tzinfo=UTC)),
            _Interval(key=2, start=datetime(2026, 7, 29, 9, 15, tzinfo=UTC), end=datetime(2026, 7, 29, 10, 0, tzinfo=UTC)),
        ]
        groups = compute_overlap_groups(intervals)
        group_ids = {groups[k][0] for k in (0, 1, 2)}
        assert len(group_ids) == 1
        assert groups[0][2] == 3

    def test_zero_duration_events_at_same_instant_are_clustered(self) -> None:
        same_start = datetime(2026, 7, 29, 8, 0, tzinfo=UTC)
        intervals = [
            _Interval(key=0, start=same_start, end=same_start),
            _Interval(key=1, start=same_start, end=same_start),
        ]
        groups = compute_overlap_groups(intervals)
        assert groups[0][0] == groups[1][0]
        assert groups[0][2] == 2


class TestBucketizeDensity:
    def test_levels_are_relative_to_the_busiest_bucket(self) -> None:
        window_start = datetime(2026, 7, 29, 0, 0, tzinfo=UTC)
        window_end = datetime(2026, 7, 29, 3, 0, tzinfo=UTC)
        starts = [
            window_start + timedelta(minutes=5),
            window_start + timedelta(hours=1, minutes=5),
            window_start + timedelta(hours=1, minutes=10),
            window_start + timedelta(hours=1, minutes=15),
        ]
        buckets = bucketize_density(starts, window_start, window_end, bucket_seconds=3600)
        assert len(buckets) == 3
        assert buckets[0].count == 1
        assert buckets[1].count == 3
        assert buckets[2].count == 0
        assert buckets[1].level == "high"
        assert buckets[2].level == "none"

    def test_empty_window_returns_no_buckets(self) -> None:
        now = datetime(2026, 7, 29, tzinfo=UTC)
        assert bucketize_density([], now, now, 3600) == []
