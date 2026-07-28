"""scheduler_resilience"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "8c9d0e1f2a3b"
down_revision = "7b8c9d0e1f2a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("task_executions", sa.Column("requirements_snapshot", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.add_column("task_executions", sa.Column("available_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("task_executions", sa.Column("scheduling_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("task_executions", sa.Column("last_scheduling_attempt_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("task_executions", sa.Column("next_scheduling_attempt_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("task_executions", sa.Column("last_scheduling_failure", JSONB(), nullable=True))
    op.create_index("ix_task_executions_available_at", "task_executions", ["available_at"])
    op.create_index("ix_task_executions_next_scheduling_attempt_at", "task_executions", ["next_scheduling_attempt_at"])
    op.create_index("ix_task_executions_scheduler_pick", "task_executions", ["status", "available_at", "priority", "created_at"])
    op.execute("UPDATE task_executions SET available_at = COALESCE(queued_at, ready_at, created_at) WHERE available_at IS NULL")

    op.add_column("resource_reservations", sa.Column("task_execution_id", sa.String(length=80), nullable=True))
    op.add_column("resource_reservations", sa.Column("units", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("resource_reservations", sa.Column("reserved_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")))
    op.add_column("resource_reservations", sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("resource_reservations", sa.Column("release_reason", sa.Text(), nullable=True))
    op.alter_column("resource_reservations", "execution_offer_id", existing_type=sa.String(length=80), nullable=True)
    op.create_foreign_key("fk_resource_reservations_task_execution_id", "resource_reservations", "task_executions", ["task_execution_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_resource_reservations_task_execution_id", "resource_reservations", ["task_execution_id"])
    op.execute(
        """
        UPDATE resource_reservations rr
        SET
            task_execution_id = ea.task_execution_id,
            units = COALESCE(rr.quantity, 1),
            reserved_at = COALESCE(rr.created_at, now()),
            activated_at = rr.converted_at,
            status = CASE
                WHEN rr.status = 'reserved' THEN 'pending'
                WHEN rr.status = 'converted' THEN 'active'
                ELSE rr.status
            END
        FROM execution_attempts ea
        WHERE rr.execution_attempt_id = ea.id
        """
    )

    op.create_table(
        "dispatch_decisions",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("scheduler_run_id", sa.String(length=80), nullable=False),
        sa.Column("task_execution_id", sa.String(length=80), nullable=False),
        sa.Column("execution_attempt_id", sa.String(length=80), nullable=True),
        sa.Column("execution_offer_id", sa.String(length=80), nullable=True),
        sa.Column("selected_agent_id", sa.String(length=80), nullable=True),
        sa.Column("selected_agent_instance_id", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("candidates", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("weights", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("metadata", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["execution_attempt_id"], ["execution_attempts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["execution_offer_id"], ["execution_offers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["selected_agent_id"], ["agents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["selected_agent_instance_id"], ["agent_instances.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_execution_id"], ["task_executions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ["scheduler_run_id", "task_execution_id", "execution_attempt_id", "execution_offer_id", "selected_agent_id", "selected_agent_instance_id", "status", "created_at"]:
        op.create_index(f"ix_dispatch_decisions_{column}", "dispatch_decisions", [column])

    op.create_table(
        "resource_locks",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("resource_key", sa.String(length=500), nullable=False),
        sa.Column("normalized_key", sa.String(length=500), nullable=False),
        sa.Column("scope", sa.String(length=120), nullable=False),
        sa.Column("agent_id", sa.String(length=80), nullable=False),
        sa.Column("execution_attempt_id", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("release_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["execution_attempt_id"], ["execution_attempts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ["normalized_key", "scope", "agent_id", "execution_attempt_id", "status", "expires_at"]:
        op.create_index(f"ix_resource_locks_{column}", "resource_locks", [column])
    op.create_index("uq_resource_locks_active_scope_key", "resource_locks", ["scope", "normalized_key"], unique=True, postgresql_where=sa.text("status = 'active'"))

    op.create_table(
        "execution_leases",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("execution_attempt_id", sa.String(length=80), nullable=False),
        sa.Column("agent_id", sa.String(length=80), nullable=False),
        sa.Column("agent_instance_id", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_renewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("renewal_sequence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("grace_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["agent_instance_id"], ["agent_instances.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["execution_attempt_id"], ["execution_attempts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ["execution_attempt_id", "agent_id", "agent_instance_id", "status", "expires_at", "grace_until"]:
        op.create_index(f"ix_execution_leases_{column}", "execution_leases", [column])
    op.create_index("uq_execution_leases_active_attempt", "execution_leases", ["execution_attempt_id"], unique=True, postgresql_where=sa.text("status IN ('active', 'suspect')"))

    op.create_table(
        "retry_schedules",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("task_execution_id", sa.String(length=80), nullable=False),
        sa.Column("source_attempt_id", sa.String(length=80), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("retry_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("error_code", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["source_attempt_id"], ["execution_attempts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_execution_id"], ["task_executions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ["task_execution_id", "source_attempt_id", "status", "available_at"]:
        op.create_index(f"ix_retry_schedules_{column}", "retry_schedules", [column])

    op.create_table(
        "cancellation_requests",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("execution_id", sa.String(length=80), nullable=False),
        sa.Column("task_execution_id", sa.String(length=80), nullable=True),
        sa.Column("execution_attempt_id", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("requested_by", sa.String(length=120), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("graceful_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("force_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("command_id", sa.String(length=80), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["command_id"], ["agent_commands.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["execution_attempt_id"], ["execution_attempts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["execution_id"], ["orchestration_executions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_execution_id"], ["task_executions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ["execution_id", "task_execution_id", "execution_attempt_id", "status", "requested_by", "graceful_until", "force_after", "command_id"]:
        op.create_index(f"ix_cancellation_requests_{column}", "cancellation_requests", [column])

    op.create_table(
        "reconciliation_records",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("kind", sa.String(length=80), nullable=False),
        sa.Column("agent_id", sa.String(length=80), nullable=True),
        sa.Column("agent_instance_id", sa.String(length=80), nullable=True),
        sa.Column("execution_attempt_id", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("decision", sa.String(length=120), nullable=False),
        sa.Column("details", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["agent_instance_id"], ["agent_instances.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["execution_attempt_id"], ["execution_attempts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ["kind", "agent_id", "agent_instance_id", "execution_attempt_id", "status", "created_at"]:
        op.create_index(f"ix_reconciliation_records_{column}", "reconciliation_records", [column])


def downgrade() -> None:
    for column in ["kind", "agent_id", "agent_instance_id", "execution_attempt_id", "status", "created_at"]:
        op.drop_index(f"ix_reconciliation_records_{column}", table_name="reconciliation_records")
    op.drop_table("reconciliation_records")

    for column in ["execution_id", "task_execution_id", "execution_attempt_id", "status", "requested_by", "graceful_until", "force_after", "command_id"]:
        op.drop_index(f"ix_cancellation_requests_{column}", table_name="cancellation_requests")
    op.drop_table("cancellation_requests")

    for column in ["task_execution_id", "source_attempt_id", "status", "available_at"]:
        op.drop_index(f"ix_retry_schedules_{column}", table_name="retry_schedules")
    op.drop_table("retry_schedules")

    op.drop_index("uq_execution_leases_active_attempt", table_name="execution_leases")
    for column in ["execution_attempt_id", "agent_id", "agent_instance_id", "status", "expires_at", "grace_until"]:
        op.drop_index(f"ix_execution_leases_{column}", table_name="execution_leases")
    op.drop_table("execution_leases")

    op.drop_index("uq_resource_locks_active_scope_key", table_name="resource_locks")
    for column in ["normalized_key", "scope", "agent_id", "execution_attempt_id", "status", "expires_at"]:
        op.drop_index(f"ix_resource_locks_{column}", table_name="resource_locks")
    op.drop_table("resource_locks")

    for column in ["scheduler_run_id", "task_execution_id", "execution_attempt_id", "execution_offer_id", "selected_agent_id", "selected_agent_instance_id", "status", "created_at"]:
        op.drop_index(f"ix_dispatch_decisions_{column}", table_name="dispatch_decisions")
    op.drop_table("dispatch_decisions")

    op.drop_index("ix_resource_reservations_task_execution_id", table_name="resource_reservations")
    op.drop_constraint("fk_resource_reservations_task_execution_id", "resource_reservations", type_="foreignkey")
    op.alter_column("resource_reservations", "execution_offer_id", existing_type=sa.String(length=80), nullable=False)
    op.drop_column("resource_reservations", "release_reason")
    op.drop_column("resource_reservations", "activated_at")
    op.drop_column("resource_reservations", "reserved_at")
    op.drop_column("resource_reservations", "units")
    op.drop_column("resource_reservations", "task_execution_id")

    op.drop_index("ix_task_executions_scheduler_pick", table_name="task_executions")
    op.drop_index("ix_task_executions_next_scheduling_attempt_at", table_name="task_executions")
    op.drop_index("ix_task_executions_available_at", table_name="task_executions")
    op.drop_column("task_executions", "last_scheduling_failure")
    op.drop_column("task_executions", "next_scheduling_attempt_at")
    op.drop_column("task_executions", "last_scheduling_attempt_at")
    op.drop_column("task_executions", "scheduling_attempts")
    op.drop_column("task_executions", "available_at")
    op.drop_column("task_executions", "requirements_snapshot")
