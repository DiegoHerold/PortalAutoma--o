"""flows_and_scheduling"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "4f5a6b7c8d9e"
down_revision = "8c9d0e1f2a3b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "flows",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("key", sa.String(length=180), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("tags", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_by", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_flows_key", "flows", ["key"], unique=True)
    op.create_index("ix_flows_category_id", "flows", ["category_id"])
    op.create_index("ix_flows_status", "flows", ["status"])
    op.create_index("ix_flows_created_by", "flows", ["created_by"])

    op.create_table(
        "flow_versions",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("flow_id", sa.String(length=80), nullable=False),
        sa.Column("version", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("definition", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("input_schema", JSONB(), nullable=True),
        sa.Column("output_schema", JSONB(), nullable=True),
        sa.Column("release_notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("published_by", sa.String(length=120), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deprecated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("blocked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["flow_id"], ["flows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("flow_id", "version", name="uq_flow_versions_flow_version"),
    )
    for column in ["flow_id", "status", "created_by", "published_at"]:
        op.create_index(f"ix_flow_versions_{column}", "flow_versions", [column])

    op.create_table(
        "flow_nodes",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("flow_version_id", sa.String(length=80), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("node_type", sa.String(length=40), nullable=False),
        sa.Column("automation_version_id", sa.Integer(), nullable=True),
        sa.Column("configuration", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("input_mapping", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("output_mapping", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("condition", JSONB(), nullable=True),
        sa.Column("retry_policy", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("timeout_policy", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("failure_policy", sa.String(length=60), nullable=False, server_default="fail_flow"),
        sa.Column("execution_policy", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("position_metadata", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["automation_version_id"], ["automation_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["flow_version_id"], ["flow_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("flow_version_id", "key", name="uq_flow_nodes_version_key"),
    )
    for column in ["flow_version_id", "node_type", "automation_version_id"]:
        op.create_index(f"ix_flow_nodes_{column}", "flow_nodes", [column])

    op.create_table(
        "flow_edges",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("flow_version_id", sa.String(length=80), nullable=False),
        sa.Column("source_node_id", sa.String(length=80), nullable=False),
        sa.Column("target_node_id", sa.String(length=80), nullable=False),
        sa.Column("edge_type", sa.String(length=40), nullable=False, server_default="success"),
        sa.Column("condition", JSONB(), nullable=True),
        sa.Column("mapping", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["flow_version_id"], ["flow_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_node_id"], ["flow_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_node_id"], ["flow_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("flow_version_id", "source_node_id", "target_node_id", "edge_type", name="uq_flow_edges_version_source_target_type"),
    )
    for column in ["flow_version_id", "source_node_id", "target_node_id"]:
        op.create_index(f"ix_flow_edges_{column}", "flow_edges", [column])

    op.create_table(
        "flow_executions",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("execution_id", sa.String(length=80), nullable=False),
        sa.Column("flow_version_id", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("origin", sa.String(length=40), nullable=False),
        sa.Column("input", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("output", JSONB(), nullable=True),
        sa.Column("requested_by", sa.String(length=120), nullable=True),
        sa.Column("schedule_execution_id", sa.String(length=80), nullable=True),
        sa.Column("correlation_id", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_summary", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["execution_id"], ["orchestration_executions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["flow_version_id"], ["flow_versions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("execution_id", name="uq_flow_executions_execution_id"),
    )
    for column in ["execution_id", "flow_version_id", "status", "origin", "requested_by", "schedule_execution_id", "correlation_id", "created_at"]:
        op.create_index(f"ix_flow_executions_{column}", "flow_executions", [column])

    op.create_table(
        "flow_node_executions",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("flow_execution_id", sa.String(length=80), nullable=False),
        sa.Column("flow_node_id", sa.String(length=80), nullable=False),
        sa.Column("task_execution_id", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("input", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("output", JSONB(), nullable=True),
        sa.Column("condition_result", JSONB(), nullable=True),
        sa.Column("dependency_state", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("skipped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_summary", sa.Text(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["flow_execution_id"], ["flow_executions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["flow_node_id"], ["flow_nodes.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["task_execution_id"], ["task_executions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("flow_execution_id", "flow_node_id", name="uq_flow_node_executions_flow_node"),
        sa.UniqueConstraint("task_execution_id", name="uq_flow_node_executions_task_execution_id"),
    )
    for column in ["flow_execution_id", "flow_node_id", "task_execution_id", "status"]:
        op.create_index(f"ix_flow_node_executions_{column}", "flow_node_executions", [column])

    op.add_column("schedules", sa.Column("key", sa.String(length=180), nullable=True))
    op.add_column("schedules", sa.Column("name", sa.String(length=180), nullable=True))
    op.add_column("schedules", sa.Column("automation_version_id", sa.Integer(), nullable=True))
    op.add_column("schedules", sa.Column("flow_id", sa.String(length=80), nullable=True))
    op.add_column("schedules", sa.Column("flow_version_id", sa.String(length=80), nullable=True))
    op.add_column("schedules", sa.Column("target_type", sa.String(length=40), nullable=False, server_default="automation"))
    op.add_column("schedules", sa.Column("status", sa.String(length=40), nullable=False, server_default="active"))
    op.add_column("schedules", sa.Column("schedule_type", sa.String(length=40), nullable=False, server_default="cron"))
    op.add_column("schedules", sa.Column("interval_seconds", sa.Integer(), nullable=True))
    op.add_column("schedules", sa.Column("payload", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.add_column("schedules", sa.Column("misfire_policy", sa.String(length=40), nullable=False, server_default="run_once_now"))
    op.add_column("schedules", sa.Column("max_catch_up_runs", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("schedules", sa.Column("misfire_grace_seconds", sa.Integer(), nullable=False, server_default="3600"))
    op.add_column("schedules", sa.Column("overlap_policy", sa.String(length=40), nullable=False, server_default="forbid"))
    op.add_column("schedules", sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("schedules", sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("schedules", sa.Column("created_by", sa.String(length=120), nullable=True))
    op.add_column("schedules", sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("schedules", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.alter_column("schedules", "automation_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("schedules", "cron_expression", existing_type=sa.String(length=80), type_=sa.String(length=120), nullable=True)
    op.create_foreign_key("fk_schedules_automation_version_id", "schedules", "automation_versions", ["automation_version_id"], ["id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_schedules_flow_id", "schedules", "flows", ["flow_id"], ["id"], ondelete="CASCADE")
    op.create_foreign_key("fk_schedules_flow_version_id", "schedules", "flow_versions", ["flow_version_id"], ["id"], ondelete="RESTRICT")
    op.execute("UPDATE schedules SET key = 'sch_' || id::text WHERE key IS NULL")
    op.execute("UPDATE schedules SET target_type = 'automation' WHERE target_type IS NULL")
    op.execute("UPDATE schedules SET status = CASE WHEN is_active THEN 'active' ELSE 'paused' END")
    op.execute("UPDATE schedules SET schedule_type = CASE WHEN is_one_time THEN 'once' ELSE 'cron' END")
    op.execute("UPDATE schedules SET next_run_at = COALESCE(last_dispatched_at, created_at) WHERE is_active = true")
    op.create_index("ix_schedules_key", "schedules", ["key"], unique=True)
    for column in ["automation_id", "automation_version_id", "flow_id", "flow_version_id", "target_type", "status", "schedule_type", "next_run_at", "created_by"]:
        op.create_index(f"ix_schedules_{column}", "schedules", [column])

    op.create_table(
        "schedule_executions",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("schedule_id", sa.Integer(), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("trigger_type", sa.String(length=40), nullable=False, server_default="scheduled"),
        sa.Column("execution_id", sa.String(length=80), nullable=True),
        sa.Column("flow_execution_id", sa.String(length=80), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result", JSONB(), nullable=True),
        sa.Column("failure_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["execution_id"], ["orchestration_executions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["flow_execution_id"], ["flow_executions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["schedule_id"], ["schedules.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("schedule_id", "scheduled_for", name="uq_schedule_executions_schedule_time"),
    )
    for column in ["schedule_id", "scheduled_for", "status", "execution_id", "flow_execution_id"]:
        op.create_index(f"ix_schedule_executions_{column}", "schedule_executions", [column])


def downgrade() -> None:
    for column in ["schedule_id", "scheduled_for", "status", "execution_id", "flow_execution_id"]:
        op.drop_index(f"ix_schedule_executions_{column}", table_name="schedule_executions")
    op.drop_table("schedule_executions")

    for column in ["automation_id", "automation_version_id", "flow_id", "flow_version_id", "target_type", "status", "schedule_type", "next_run_at", "created_by"]:
        op.drop_index(f"ix_schedules_{column}", table_name="schedules")
    op.drop_index("ix_schedules_key", table_name="schedules")
    op.drop_constraint("fk_schedules_flow_version_id", "schedules", type_="foreignkey")
    op.drop_constraint("fk_schedules_flow_id", "schedules", type_="foreignkey")
    op.drop_constraint("fk_schedules_automation_version_id", "schedules", type_="foreignkey")
    op.alter_column("schedules", "cron_expression", existing_type=sa.String(length=120), type_=sa.String(length=80), nullable=False)
    op.alter_column("schedules", "automation_id", existing_type=sa.Integer(), nullable=False)
    for column in [
        "archived_at",
        "paused_at",
        "created_by",
        "last_run_at",
        "next_run_at",
        "overlap_policy",
        "misfire_grace_seconds",
        "max_catch_up_runs",
        "misfire_policy",
        "payload",
        "interval_seconds",
        "schedule_type",
        "status",
        "target_type",
        "flow_version_id",
        "flow_id",
        "automation_version_id",
        "name",
        "key",
    ]:
        op.drop_column("schedules", column)

    for column in ["flow_execution_id", "flow_node_id", "task_execution_id", "status"]:
        op.drop_index(f"ix_flow_node_executions_{column}", table_name="flow_node_executions")
    op.drop_table("flow_node_executions")

    for column in ["execution_id", "flow_version_id", "status", "origin", "requested_by", "schedule_execution_id", "correlation_id", "created_at"]:
        op.drop_index(f"ix_flow_executions_{column}", table_name="flow_executions")
    op.drop_table("flow_executions")

    for column in ["flow_version_id", "source_node_id", "target_node_id"]:
        op.drop_index(f"ix_flow_edges_{column}", table_name="flow_edges")
    op.drop_table("flow_edges")

    for column in ["flow_version_id", "node_type", "automation_version_id"]:
        op.drop_index(f"ix_flow_nodes_{column}", table_name="flow_nodes")
    op.drop_table("flow_nodes")

    for column in ["flow_id", "status", "created_by", "published_at"]:
        op.drop_index(f"ix_flow_versions_{column}", table_name="flow_versions")
    op.drop_table("flow_versions")

    op.drop_index("ix_flows_created_by", table_name="flows")
    op.drop_index("ix_flows_status", table_name="flows")
    op.drop_index("ix_flows_category_id", table_name="flows")
    op.drop_index("ix_flows_key", table_name="flows")
    op.drop_table("flows")
