"""
Periodic Celery Beat task: dispatches a Job for every Schedule that has a due
cron occurrence since it last fired. This used to be a stub ("return ok") --
Schedules were pure cadastro with nothing ever actually reading them.

Runs every minute (see beat_schedule in app/core/celery_app.py).
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from croniter import croniter

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.schedule import Schedule
from app.schemas.job import JobCreate
from app.services.job_dispatcher_service import JobDispatcherService
from app.utils.datetime import utcnow

DEFAULT_TIMEZONE = "America/Sao_Paulo"
# How far back to look for a due occurrence on a schedule that has never
# fired yet. Comfortably larger than the beat interval (60s) so a slow tick
# never causes a missed dispatch.
FIRST_RUN_LOOKBACK = timedelta(minutes=2)


@celery_app.task(name="app.tasks.schedule_tasks.sync")
def sync_schedules() -> str:
    now = utcnow()
    dispatched: list[int] = []
    errors: list[str] = []

    with SessionLocal() as db:
        schedules = db.query(Schedule).filter(Schedule.is_active.is_(True)).all()
        for schedule in schedules:
            try:
                if _is_due(schedule, now):
                    dispatcher = JobDispatcherService(db)
                    dispatcher.dispatch_system(
                        JobCreate(automation_id=schedule.automation_id, payload_json={}),
                        schedule_id=schedule.id,
                    )
                    schedule.last_dispatched_at = now
                    if schedule.is_one_time:
                        schedule.is_active = False
                    db.commit()
                    dispatched.append(schedule.id)
            except Exception as exc:  # noqa: BLE001 -- one bad schedule must not block the rest
                db.rollback()
                errors.append(f"schedule {schedule.id}: {exc}")

    return f"dispatched={dispatched} errors={errors}"


def _is_due(schedule: Schedule, now: datetime) -> bool:
    try:
        tz = ZoneInfo(schedule.timezone)
    except Exception:
        tz = ZoneInfo(DEFAULT_TIMEZONE)

    now_local = now.astimezone(tz)
    lookback = schedule.last_dispatched_at or (now - FIRST_RUN_LOOKBACK)
    lookback_local = lookback.astimezone(tz)

    iterator = croniter(schedule.cron_expression, lookback_local)
    next_fire = iterator.get_next(datetime)
    # If a schedule fell behind by a lot (beat was down, etc.), only the
    # single next-due occurrence is dispatched -- last_dispatched_at jumps to
    # "now" below, not to next_fire, so any earlier backlog is skipped
    # rather than replayed all at once.
    return next_fire <= now_local
