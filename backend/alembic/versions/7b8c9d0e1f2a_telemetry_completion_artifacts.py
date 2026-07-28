"""telemetry_completion_artifacts"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "7b8c9d0e1f2a"
down_revision = "6a7b8c9d0e1f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("execution_attempts", sa.Column("exit_code", sa.Integer(), nullable=True))
    op.add_column("execution_attempts", sa.Column("output", JSONB(), nullable=True))
    op.add_column("execution_attempts", sa.Column("result", JSONB(), nullable=True))
    op.add_column("execution_attempts", sa.Column("resource_usage", JSONB(), nullable=True))

    op.create_table(
        "execution_events",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("execution_id", sa.String(length=80), nullable=False),
        sa.Column("task_execution_id", sa.String(length=80), nullable=False),
        sa.Column("execution_attempt_id", sa.String(length=80), nullable=False),
        sa.Column("agent_id", sa.String(length=80), nullable=False),
        sa.Column("agent_instance_id", sa.String(length=80), nullable=False),
        sa.Column("event_sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("level", sa.String(length=20), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("payload", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("message_id", sa.String(length=120), nullable=True),
        sa.Column("correlation_id", sa.String(length=120), nullable=True),
        sa.Column("causation_id", sa.String(length=120), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["agent_instance_id"], ["agent_instances.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["execution_attempt_id"], ["execution_attempts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["execution_id"], ["orchestration_executions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_execution_id"], ["task_executions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("execution_attempt_id", "event_sequence", name="uq_execution_events_attempt_sequence"),
    )
    for column in ["execution_id", "task_execution_id", "execution_attempt_id", "agent_id", "agent_instance_id", "event_type", "level", "received_at", "message_id", "correlation_id", "causation_id"]:
        op.create_index(f"ix_execution_events_{column}", "execution_events", [column])
    op.create_index("ix_execution_events_execution_received", "execution_events", ["execution_id", "received_at"])
    op.create_index("ix_execution_events_task_received", "execution_events", ["task_execution_id", "received_at"])
    op.create_index("ix_execution_events_attempt_sequence", "execution_events", ["execution_attempt_id", "event_sequence"])
    op.create_index("ix_execution_events_agent_received", "execution_events", ["agent_id", "received_at"])
    op.create_index("ix_execution_events_type_received", "execution_events", ["event_type", "received_at"])
    op.create_index("ix_execution_events_level_received", "execution_events", ["level", "received_at"])

    op.create_table(
        "event_acknowledgements",
        sa.Column("execution_attempt_id", sa.String(length=80), nullable=False),
        sa.Column("highest_received_sequence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("highest_contiguous_sequence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("missing_ranges", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("duplicate_sequences", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["execution_attempt_id"], ["execution_attempts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("execution_attempt_id"),
    )

    op.create_table(
        "execution_metrics",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("event_id", sa.String(length=80), nullable=False),
        sa.Column("execution_id", sa.String(length=80), nullable=False),
        sa.Column("task_execution_id", sa.String(length=80), nullable=False),
        sa.Column("execution_attempt_id", sa.String(length=80), nullable=False),
        sa.Column("event_sequence", sa.Integer(), nullable=False),
        sa.Column("metric_name", sa.String(length=120), nullable=False),
        sa.Column("metric_type", sa.String(length=40), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=40), nullable=True),
        sa.Column("labels", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["execution_events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["execution_attempt_id"], ["execution_attempts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["execution_id"], ["orchestration_executions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_execution_id"], ["task_executions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("execution_attempt_id", "event_sequence", "metric_name", name="uq_execution_metrics_attempt_sequence_name"),
    )
    for column in ["event_id", "execution_id", "task_execution_id", "execution_attempt_id", "metric_name", "received_at"]:
        op.create_index(f"ix_execution_metrics_{column}", "execution_metrics", [column])
    op.create_index("ix_execution_metrics_execution_received", "execution_metrics", ["execution_id", "received_at"])
    op.create_index("ix_execution_metrics_attempt_name_received", "execution_metrics", ["execution_attempt_id", "metric_name", "received_at"])
    op.create_index("ix_execution_metrics_name_received", "execution_metrics", ["metric_name", "received_at"])

    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("execution_id", sa.String(length=80), nullable=False),
        sa.Column("task_execution_id", sa.String(length=80), nullable=False),
        sa.Column("execution_attempt_id", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("stored_object_id", sa.String(length=36), nullable=True),
        sa.Column("upload_session_id", sa.String(length=36), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("metadata", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["execution_attempt_id"], ["execution_attempts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["execution_id"], ["orchestration_executions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stored_object_id"], ["stored_objects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_execution_id"], ["task_executions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["upload_session_id"], ["upload_sessions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ["execution_id", "task_execution_id", "execution_attempt_id", "status", "stored_object_id", "upload_session_id", "sha256"]:
        op.create_index(f"ix_artifacts_{column}", "artifacts", [column])
    op.create_index("ix_artifacts_execution_created", "artifacts", ["execution_id", "created_at"])
    op.create_index("ix_artifacts_attempt_status", "artifacts", ["execution_attempt_id", "status"])

    op.create_table(
        "artifact_upload_sessions",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("artifact_id", sa.String(length=80), nullable=False),
        sa.Column("upload_session_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["artifact_id"], ["artifacts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["upload_session_id"], ["upload_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("artifact_id", "upload_session_id", name="uq_artifact_upload_session_pair"),
        sa.UniqueConstraint("upload_session_id", name="uq_artifact_upload_session_upload"),
    )
    op.create_index("ix_artifact_upload_sessions_artifact_id", "artifact_upload_sessions", ["artifact_id"])
    op.create_index("ix_artifact_upload_sessions_upload_session_id", "artifact_upload_sessions", ["upload_session_id"])


def downgrade() -> None:
    op.drop_index("ix_artifact_upload_sessions_upload_session_id", table_name="artifact_upload_sessions")
    op.drop_index("ix_artifact_upload_sessions_artifact_id", table_name="artifact_upload_sessions")
    op.drop_table("artifact_upload_sessions")

    op.drop_index("ix_artifacts_attempt_status", table_name="artifacts")
    op.drop_index("ix_artifacts_execution_created", table_name="artifacts")
    for column in ["execution_id", "task_execution_id", "execution_attempt_id", "status", "stored_object_id", "upload_session_id", "sha256"]:
        op.drop_index(f"ix_artifacts_{column}", table_name="artifacts")
    op.drop_table("artifacts")

    op.drop_index("ix_execution_metrics_name_received", table_name="execution_metrics")
    op.drop_index("ix_execution_metrics_attempt_name_received", table_name="execution_metrics")
    op.drop_index("ix_execution_metrics_execution_received", table_name="execution_metrics")
    for column in ["event_id", "execution_id", "task_execution_id", "execution_attempt_id", "metric_name", "received_at"]:
        op.drop_index(f"ix_execution_metrics_{column}", table_name="execution_metrics")
    op.drop_table("execution_metrics")

    op.drop_table("event_acknowledgements")

    op.drop_index("ix_execution_events_level_received", table_name="execution_events")
    op.drop_index("ix_execution_events_type_received", table_name="execution_events")
    op.drop_index("ix_execution_events_agent_received", table_name="execution_events")
    op.drop_index("ix_execution_events_attempt_sequence", table_name="execution_events")
    op.drop_index("ix_execution_events_task_received", table_name="execution_events")
    op.drop_index("ix_execution_events_execution_received", table_name="execution_events")
    for column in ["execution_id", "task_execution_id", "execution_attempt_id", "agent_id", "agent_instance_id", "event_type", "level", "received_at", "message_id", "correlation_id", "causation_id"]:
        op.drop_index(f"ix_execution_events_{column}", table_name="execution_events")
    op.drop_table("execution_events")

    op.drop_column("execution_attempts", "resource_usage")
    op.drop_column("execution_attempts", "result")
    op.drop_column("execution_attempts", "output")
    op.drop_column("execution_attempts", "exit_code")
