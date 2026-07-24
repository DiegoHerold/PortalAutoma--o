"""schedule_recurrence_trigger_mapping"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "7c1d8e4f9a3b"
down_revision = "3a7c1e9f2b04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Schedule: structured recurrence fields (cron_expression stays as the
    # computed, authoritative field used for dispatch/calendar math).
    op.add_column("schedules", sa.Column("recurrence_type", sa.String(length=20), nullable=False, server_default="daily"))
    op.add_column("schedules", sa.Column("weekdays_json", JSONB(), nullable=True))
    op.add_column("schedules", sa.Column("day_of_month", sa.Integer(), nullable=True))
    op.add_column("schedules", sa.Column("time_of_day", sa.String(length=5), nullable=False, server_default="08:00"))
    op.add_column("schedules", sa.Column("specific_date", sa.Date(), nullable=True))
    op.add_column("schedules", sa.Column("is_one_time", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("schedules", sa.Column("last_dispatched_at", sa.DateTime(timezone=True), nullable=True))
    op.alter_column("schedules", "recurrence_type", server_default=None)
    op.alter_column("schedules", "time_of_day", server_default=None)
    op.alter_column("schedules", "is_one_time", server_default=None)

    # Job: link back to whatever created it (schedule or trigger), so the
    # calendar can show "already ran" per occurrence and chaining can avoid
    # double-firing.
    op.add_column("jobs", sa.Column("schedule_id", sa.Integer(), nullable=True))
    op.add_column("jobs", sa.Column("trigger_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_jobs_schedule_id", "jobs", "schedules", ["schedule_id"], ["id"])
    op.create_foreign_key("fk_jobs_trigger_id", "jobs", "triggers", ["trigger_id"], ["id"])
    op.create_index(op.f("ix_jobs_schedule_id"), "jobs", ["schedule_id"])
    op.create_index(op.f("ix_jobs_trigger_id"), "jobs", ["trigger_id"])

    # Trigger: payload -> parameter mapping, UI template tag, and the fields
    # needed for the new "chained" trigger type (source automation +
    # condition). secret_token already exists and is now the only thing
    # webhook validation checks (config_json never existed as a real column).
    op.add_column("triggers", sa.Column("parameter_mapping_json", JSONB(), nullable=True))
    op.add_column("triggers", sa.Column("template", sa.String(length=50), nullable=True))
    op.add_column("triggers", sa.Column("source_automation_id", sa.Integer(), nullable=True))
    op.add_column("triggers", sa.Column("condition", sa.String(length=20), nullable=True))
    op.create_foreign_key(
        "fk_triggers_source_automation_id", "triggers", "automations", ["source_automation_id"], ["id"]
    )
    op.create_index(op.f("ix_triggers_source_automation_id"), "triggers", ["source_automation_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_triggers_source_automation_id"), table_name="triggers")
    op.drop_constraint("fk_triggers_source_automation_id", "triggers", type_="foreignkey")
    op.drop_column("triggers", "condition")
    op.drop_column("triggers", "source_automation_id")
    op.drop_column("triggers", "template")
    op.drop_column("triggers", "parameter_mapping_json")

    op.drop_index(op.f("ix_jobs_trigger_id"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_schedule_id"), table_name="jobs")
    op.drop_constraint("fk_jobs_trigger_id", "jobs", type_="foreignkey")
    op.drop_constraint("fk_jobs_schedule_id", "jobs", type_="foreignkey")
    op.drop_column("jobs", "trigger_id")
    op.drop_column("jobs", "schedule_id")

    op.drop_column("schedules", "last_dispatched_at")
    op.drop_column("schedules", "is_one_time")
    op.drop_column("schedules", "specific_date")
    op.drop_column("schedules", "time_of_day")
    op.drop_column("schedules", "day_of_month")
    op.drop_column("schedules", "weekdays_json")
    op.drop_column("schedules", "recurrence_type")
