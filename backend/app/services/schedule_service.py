from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from croniter import croniter
from sqlalchemy.orm import Session

from app.core.constants import JobStatus
from app.domain.recurrence import RecurrenceError, RecurrenceInput, build_cron_expression
from app.models.job import Job
from app.models.schedule import Schedule
from app.models.user import User
from app.repositories.automation_repository import AutomationRepository
from app.repositories.schedule_repository import ScheduleRepository
from app.schemas.schedule import ScheduleCreate, ScheduleUpdate
from app.services.audit_service import AuditService
from app.services.permission_service import PermissionService
from app.utils.datetime import utcnow

DEFAULT_TIMEZONE = "America/Sao_Paulo"
MAX_CALENDAR_OCCURRENCES_PER_SCHEDULE = 500  # safety cap against a bad cron generating a huge range

_JOB_STATUS_TO_OCCURRENCE_STATUS = {
    JobStatus.PENDING: "queued",
    JobStatus.QUEUED: "queued",
    JobStatus.RUNNING: "running",
    JobStatus.SUCCESS: "success",
    JobStatus.FAILED: "failed",
    JobStatus.CANCELLED: "cancelled",
}


def _apply_recurrence_fields(schedule: Schedule, payload: ScheduleCreate) -> None:
    try:
        cron_expression = build_cron_expression(
            RecurrenceInput(
                recurrence_type=payload.recurrence_type,
                time_of_day=payload.time_of_day,
                weekdays=payload.weekdays,
                day_of_month=payload.day_of_month,
                specific_date=payload.specific_date,
            )
        )
    except RecurrenceError as exc:
        raise ValueError(str(exc)) from exc

    schedule.automation_id = payload.automation_id
    schedule.timezone = payload.timezone
    schedule.is_active = payload.is_active
    schedule.recurrence_type = payload.recurrence_type
    schedule.time_of_day = payload.time_of_day
    schedule.weekdays_json = payload.weekdays
    schedule.day_of_month = payload.day_of_month
    schedule.specific_date = payload.specific_date
    schedule.is_one_time = payload.recurrence_type == "once"
    schedule.cron_expression = cron_expression


class ScheduleService:
    def __init__(self, db: Session) -> None:
        self.audit = AuditService(db)
        self.automations = AutomationRepository(db)
        self.db = db
        self.permissions = PermissionService(db)
        self.schedules = ScheduleRepository(db)

    def list_schedules(self):
        return self.schedules.list_all()

    def get_calendar_occurrences(self, from_date: date, to_date: date) -> list[dict]:
        """
        Every occurrence of every active Schedule that falls between
        from_date and to_date (inclusive, in each schedule's own timezone),
        merged with the Job it actually produced (if the occurrence is in
        the past) so the calendar can show agendado/rodando/sucesso/falha.
        """
        schedules = [s for s in self.schedules.list_all() if s.is_active]
        automation_ids = {s.automation_id for s in schedules}
        automations = {a.id: a for a in self.automations.list_all() if a.id in automation_ids}
        now = utcnow()

        occurrences: list[dict] = []
        for schedule in schedules:
            automation = automations.get(schedule.automation_id)
            if automation is None:
                continue
            occurrences.extend(self._occurrences_for_schedule(schedule, automation, from_date, to_date, now))

        occurrences.sort(key=lambda item: item["occurs_at"])
        return occurrences

    def _occurrences_for_schedule(self, schedule: Schedule, automation, from_date: date, to_date: date, now: datetime) -> list[dict]:
        try:
            tz = ZoneInfo(schedule.timezone)
        except Exception:
            tz = ZoneInfo(DEFAULT_TIMEZONE)

        range_start = datetime.combine(from_date, time.min, tzinfo=tz)
        range_end = datetime.combine(to_date, time.max, tzinfo=tz)

        results: list[dict] = []
        iterator = croniter(schedule.cron_expression, range_start - timedelta(seconds=1))
        for _ in range(MAX_CALENDAR_OCCURRENCES_PER_SCHEDULE):
            occurs_at = iterator.get_next(datetime)
            if occurs_at > range_end:
                break
            results.append(self._build_occurrence(schedule, automation, occurs_at, now))
            if schedule.is_one_time:
                break
        return results

    def _build_occurrence(self, schedule: Schedule, automation, occurs_at: datetime, now: datetime) -> dict:
        status = "upcoming"
        job_id = None
        if occurs_at <= now:
            status = "missed"
            occurs_date = occurs_at.date()
            recent_jobs = (
                self.db.query(Job)
                .filter(Job.schedule_id == schedule.id)
                .order_by(Job.created_at.desc())
                .limit(20)
                .all()
            )
            matched = next(
                (j for j in recent_jobs if j.created_at and j.created_at.astimezone(occurs_at.tzinfo).date() == occurs_date),
                None,
            )
            if matched is not None:
                job_id = matched.id
                status = _JOB_STATUS_TO_OCCURRENCE_STATUS.get(matched.status, "queued")

        return {
            "schedule_id": schedule.id,
            "automation_id": automation.id,
            "automation_name": automation.name,
            "category_id": automation.category_id,
            "recurrence_type": schedule.recurrence_type,
            "occurs_at": occurs_at.isoformat(),
            "status": status,
            "job_id": job_id,
        }

    def create_schedule(self, user: User, payload: ScheduleCreate) -> Schedule:
        automation = self.automations.get(payload.automation_id)
        if automation is None:
            raise ValueError("Automation not found.")
        self.permissions.ensure_category_action(user, automation.category_id, "can_create")
        schedule = Schedule()
        _apply_recurrence_fields(schedule, payload)
        schedule = self.schedules.create(schedule)
        self.audit.record(
            "schedule_created",
            actor_email=user.email,
            resource_type="schedule",
            resource_id=str(schedule.id),
            details=schedule.cron_expression,
        )
        self.db.commit()
        return schedule

    def update_schedule(self, user: User, schedule_id: int, payload: ScheduleUpdate) -> Schedule:
        schedule = self.schedules.get(schedule_id)
        if schedule is None:
            raise ValueError("Schedule not found.")
        current_automation = self.automations.get(schedule.automation_id)
        if current_automation is None:
            raise ValueError("Automation not found.")
        new_automation = self.automations.get(payload.automation_id)
        if new_automation is None:
            raise ValueError("Automation not found.")
        self.permissions.ensure_category_action(user, current_automation.category_id, "can_edit")
        self.permissions.ensure_category_action(user, new_automation.category_id, "can_edit")
        _apply_recurrence_fields(schedule, payload)
        updated = self.schedules.update(schedule)
        self.audit.record(
            "schedule_updated",
            actor_email=user.email,
            resource_type="schedule",
            resource_id=str(updated.id),
            details=updated.cron_expression,
        )
        self.db.commit()
        return updated

    def delete_schedule(self, user: User, schedule_id: int) -> None:
        schedule = self.schedules.get(schedule_id)
        if schedule is None:
            raise ValueError("Schedule not found.")
        automation = self.automations.get(schedule.automation_id)
        if automation is None:
            raise ValueError("Automation not found.")
        self.permissions.ensure_category_action(user, automation.category_id, "can_delete")
        self.audit.record(
            "schedule_deleted",
            actor_email=user.email,
            resource_type="schedule",
            resource_id=str(schedule.id),
            details=schedule.cron_expression,
        )
        self.schedules.delete(schedule)
