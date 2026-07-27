"""execution_dispatch_minimum"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "6a7b8c9d0e1f"
down_revision = "1f2a3b4c5d6e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "orchestration_executions",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("type", sa.String(length=40), nullable=False),
        sa.Column("origin", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("requested_by", sa.String(length=120), nullable=True),
        sa.Column("organization_id", sa.String(length=120), nullable=True),
        sa.Column("input", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("result", JSONB(), nullable=True),
        sa.Column("correlation_id", sa.String(length=120), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_summary", sa.Text(), nullable=True),
        sa.Column("legacy_job_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["legacy_job_id"], ["jobs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("legacy_job_id", name="uq_orchestration_executions_legacy_job_id"),
    )
    for column in ["origin", "status", "requested_by", "organization_id", "correlation_id", "idempotency_key", "created_at"]:
        op.create_index(f"ix_orchestration_executions_{column}", "orchestration_executions", [column])
    op.create_index("ix_orchestration_executions_status_created_at", "orchestration_executions", ["status", "created_at"])

    op.create_table(
        "task_executions",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("execution_id", sa.String(length=80), nullable=False),
        sa.Column("automation_version_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("parameters", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("input", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("result", JSONB(), nullable=True),
        sa.Column("retry_policy", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("timeout_policy", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_attempt_number", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_summary", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["automation_version_id"], ["automation_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["execution_id"], ["orchestration_executions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ["execution_id", "automation_version_id", "status"]:
        op.create_index(f"ix_task_executions_{column}", "task_executions", [column])
    op.create_index("ix_task_executions_execution_id_status", "task_executions", ["execution_id", "status"])

    op.create_table(
        "execution_attempts",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("task_execution_id", sa.String(length=80), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.String(length=80), nullable=False),
        sa.Column("agent_instance_id", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("runtime_version_id", sa.String(length=36), nullable=True),
        sa.Column("package_id", sa.String(length=36), nullable=True),
        sa.Column("offer_id", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("offered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("preparing_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=120), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["agent_instance_id"], ["agent_instances.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["package_id"], ["automation_packages.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["runtime_version_id"], ["runtime_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["task_execution_id"], ["task_executions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_execution_id", "attempt_number", name="uq_execution_attempt_task_number"),
    )
    for column in ["task_execution_id", "agent_id", "agent_instance_id", "status", "runtime_version_id", "package_id", "offer_id"]:
        op.create_index(f"ix_execution_attempts_{column}", "execution_attempts", [column])
    op.create_index("ix_execution_attempts_task_execution_id_attempt_number", "execution_attempts", ["task_execution_id", "attempt_number"])
    op.create_index("ix_execution_attempts_agent_id_status", "execution_attempts", ["agent_id", "status"])

    op.create_table(
        "execution_offers",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("execution_attempt_id", sa.String(length=80), nullable=False),
        sa.Column("agent_id", sa.String(length=80), nullable=False),
        sa.Column("agent_instance_id", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("requirements_snapshot", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("offered_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_code", sa.String(length=120), nullable=True),
        sa.Column("rejection_details", JSONB(), nullable=True),
        sa.Column("correlation_id", sa.String(length=120), nullable=True),
        sa.Column("commit_token_hash", sa.String(length=64), nullable=True),
        sa.Column("commit_token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["agent_instance_id"], ["agent_instances.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["execution_attempt_id"], ["execution_attempts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ["execution_attempt_id", "agent_id", "agent_instance_id", "status", "expires_at", "correlation_id"]:
        op.create_index(f"ix_execution_offers_{column}", "execution_offers", [column])
    op.create_index("ix_execution_offers_execution_attempt_id_status", "execution_offers", ["execution_attempt_id", "status"])
    op.create_index("ix_execution_offers_agent_id_status_expires_at", "execution_offers", ["agent_id", "status", "expires_at"])

    op.create_table(
        "resource_reservations",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("execution_offer_id", sa.String(length=80), nullable=False),
        sa.Column("execution_attempt_id", sa.String(length=80), nullable=False),
        sa.Column("agent_id", sa.String(length=80), nullable=False),
        sa.Column("agent_instance_id", sa.String(length=80), nullable=False),
        sa.Column("pool_type", sa.String(length=40), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("converted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["agent_instance_id"], ["agent_instances.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["execution_attempt_id"], ["execution_attempts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["execution_offer_id"], ["execution_offers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ["execution_offer_id", "execution_attempt_id", "agent_id", "agent_instance_id", "pool_type", "status", "expires_at"]:
        op.create_index(f"ix_resource_reservations_{column}", "resource_reservations", [column])


def downgrade() -> None:
    for column in ["execution_offer_id", "execution_attempt_id", "agent_id", "agent_instance_id", "pool_type", "status", "expires_at"]:
        op.drop_index(f"ix_resource_reservations_{column}", table_name="resource_reservations")
    op.drop_table("resource_reservations")

    op.drop_index("ix_execution_offers_agent_id_status_expires_at", table_name="execution_offers")
    op.drop_index("ix_execution_offers_execution_attempt_id_status", table_name="execution_offers")
    for column in ["execution_attempt_id", "agent_id", "agent_instance_id", "status", "expires_at", "correlation_id"]:
        op.drop_index(f"ix_execution_offers_{column}", table_name="execution_offers")
    op.drop_table("execution_offers")

    op.drop_index("ix_execution_attempts_agent_id_status", table_name="execution_attempts")
    op.drop_index("ix_execution_attempts_task_execution_id_attempt_number", table_name="execution_attempts")
    for column in ["task_execution_id", "agent_id", "agent_instance_id", "status", "runtime_version_id", "package_id", "offer_id"]:
        op.drop_index(f"ix_execution_attempts_{column}", table_name="execution_attempts")
    op.drop_table("execution_attempts")

    op.drop_index("ix_task_executions_execution_id_status", table_name="task_executions")
    for column in ["execution_id", "automation_version_id", "status"]:
        op.drop_index(f"ix_task_executions_{column}", table_name="task_executions")
    op.drop_table("task_executions")

    op.drop_index("ix_orchestration_executions_status_created_at", table_name="orchestration_executions")
    for column in ["origin", "status", "requested_by", "organization_id", "correlation_id", "idempotency_key", "created_at"]:
        op.drop_index(f"ix_orchestration_executions_{column}", table_name="orchestration_executions")
    op.drop_table("orchestration_executions")
