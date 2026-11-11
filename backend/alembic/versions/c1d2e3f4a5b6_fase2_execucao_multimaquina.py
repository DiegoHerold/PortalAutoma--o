"""Fase 2: máquina, executor genérico, itens, histórico de etapas e estimativas.

Aditiva (ADR-018, ADR-019): nada é apagado. Colunas de Agent viram anuláveis; cada Agent
existente ganha a sua máquina; tentativas e eventos existentes ficam com executor "agent".

Revision ID: c1d2e3f4a5b6
Revises: b6c7d8e9f001
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c1d2e3f4a5b6"
down_revision = "b6c7d8e9f001"
branch_labels = None
depends_on = None

JSONB = postgresql.JSONB(astext_type=sa.Text())


def _agora() -> sa.TextClause:
    return sa.text("now()")


def upgrade() -> None:
    # -- Fleet: máquina e instância direta ---------------------------------------------
    op.create_table(
        "machines",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("hostname", sa.String(180), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="ativa"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_agora()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=_agora()),
        sa.UniqueConstraint("name", name="uq_machines_name"),
    )
    op.add_column("agents", sa.Column("machine_id", sa.String(80), sa.ForeignKey("machines.id"), nullable=True))
    op.create_index("ix_agents_machine_id", "agents", ["machine_id"])
    op.execute("""
        INSERT INTO machines (id, name, hostname, status, notes)
        SELECT 'mch_' || a.id,
               CASE WHEN EXISTS (SELECT 1 FROM agents o WHERE o.name = a.name AND o.id <> a.id)
                    THEN a.name || ' (' || a.id || ')' ELSE a.name END,
               a.hostname, 'ativa', 'Criada pela migração da Fase 2 a partir do Agent ' || a.id
        FROM agents a
    """)
    op.execute("UPDATE agents SET machine_id = 'mch_' || id")

    op.create_table(
        "direct_instances",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("automation_id", sa.Integer(), sa.ForeignKey("automations.id"), nullable=False),
        sa.Column("machine_id", sa.String(80), sa.ForeignKey("machines.id"), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="pendente"),
        sa.Column("reported_name", sa.String(255), nullable=True),
        sa.Column("reported_version", sa.String(80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_agora()),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.String(120), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('pendente', 'aprovada', 'quarentena', 'revogada')", name="ck_direct_instances_status"),
        sa.CheckConstraint("status = 'pendente' OR machine_id IS NOT NULL", name="ck_direct_instances_machine_after_approval"),
    )
    op.create_index("ix_direct_instances_automation", "direct_instances", ["automation_id"])
    op.create_index("ix_direct_instances_machine", "direct_instances", ["machine_id"])

    # -- Orchestration: executor genérico na tentativa ---------------------------------
    op.add_column("execution_attempts", sa.Column("executor_type", sa.String(20), nullable=False, server_default="agent"))
    op.add_column("execution_attempts", sa.Column("executor_id", sa.String(80), nullable=True))
    op.add_column("execution_attempts", sa.Column("machine_id", sa.String(80), sa.ForeignKey("machines.id"), nullable=True))
    op.alter_column("execution_attempts", "agent_id", existing_type=sa.String(80), nullable=True)
    op.alter_column("execution_attempts", "agent_instance_id", existing_type=sa.String(80), nullable=True)
    op.execute("""
        UPDATE execution_attempts t SET executor_id = t.agent_id, machine_id = a.machine_id
        FROM agents a WHERE a.id = t.agent_id
    """)
    op.create_check_constraint(
        "ck_execution_attempts_executor", "execution_attempts",
        "(executor_type = 'agent' AND agent_id IS NOT NULL AND agent_instance_id IS NOT NULL) "
        "OR (executor_type = 'direct' AND executor_id IS NOT NULL AND agent_id IS NULL)",
    )
    op.create_index("ix_execution_attempts_machine", "execution_attempts", ["machine_id"])
    op.create_index("ix_execution_attempts_executor", "execution_attempts", ["executor_type", "executor_id"])

    op.create_table(
        "execution_items",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("execution_id", sa.String(80), sa.ForeignKey("orchestration_executions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_execution_id", sa.String(80), sa.ForeignKey("task_executions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("automation_id", sa.Integer(), sa.ForeignKey("automations.id"), nullable=False),
        sa.Column("item_key", sa.String(120), nullable=False),
        sa.Column("label", sa.String(200), nullable=True),
        sa.Column("group_key", sa.String(120), nullable=True),
        sa.Column("configuration", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("work_signature", sa.String(64), nullable=False, server_default=""),
        sa.Column("status", sa.String(30), nullable=False, server_default="pendente"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("attention", JSONB, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=_agora()),
        sa.UniqueConstraint("task_execution_id", "item_key", name="uq_execution_items_task_item"),
        sa.CheckConstraint("status IN ('pendente', 'executando', 'ok', 'erro', 'atencao', 'cancelado', 'ignorado')",
                           name="ck_execution_items_status"),
    )
    op.create_index("ix_execution_items_execution", "execution_items", ["execution_id"])
    op.create_index("ix_execution_items_automation_item", "execution_items", ["automation_id", "item_key"])

    op.create_table(
        "step_plans",
        sa.Column("task_execution_id", sa.String(80), sa.ForeignKey("task_executions.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("item_key", sa.String(120), primary_key=True),  # "" = etapa sem item
        sa.Column("step_key", sa.String(120), primary_key=True),
        sa.Column("planned_tasks", sa.Integer(), nullable=True),
        sa.Column("completed_tasks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=_agora()),
    )

    # -- Telemetry: eventos sem Agent, histórico de etapas, pausas e estimativas ----------
    op.add_column("execution_events", sa.Column("executor_type", sa.String(20), nullable=False, server_default="agent"))
    op.add_column("execution_events", sa.Column("executor_id", sa.String(80), nullable=True))
    op.alter_column("execution_events", "agent_id", existing_type=sa.String(80), nullable=True)
    op.alter_column("execution_events", "agent_instance_id", existing_type=sa.String(80), nullable=True)
    op.execute("UPDATE execution_events SET executor_id = agent_id")

    op.create_table(
        "step_runs",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("execution_id", sa.String(80), sa.ForeignKey("orchestration_executions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_execution_id", sa.String(80), sa.ForeignKey("task_executions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("execution_attempt_id", sa.String(80), sa.ForeignKey("execution_attempts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("automation_id", sa.Integer(), nullable=False),
        sa.Column("automation_version_id", sa.Integer(), nullable=False),
        sa.Column("step_key", sa.String(120), nullable=False),
        sa.Column("item_key", sa.String(120), nullable=True),
        sa.Column("work_signature", sa.String(64), nullable=False, server_default=""),
        sa.Column("status", sa.String(30), nullable=False, server_default="executando"),
        sa.Column("planned_tasks", sa.Integer(), nullable=True),
        sa.Column("tasks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("gross_seconds", sa.Float(), nullable=True),
        sa.Column("paused_seconds", sa.Float(), nullable=False, server_default="0"),
        sa.Column("net_seconds", sa.Float(), nullable=True),
        sa.Column("machine_id", sa.String(80), nullable=True),
        sa.Column("executor_type", sa.String(20), nullable=False, server_default="agent"),
        sa.Column("start_sequence", sa.Integer(), nullable=False),
        sa.UniqueConstraint("execution_attempt_id", "start_sequence", name="uq_step_runs_attempt_sequence"),
        sa.CheckConstraint("status IN ('executando', 'ok', 'erro', 'interrompida')", name="ck_step_runs_status"),
    )
    op.create_index("ix_step_runs_history", "step_runs", ["automation_id", "step_key", "item_key", "completed_at"])
    op.create_index("ix_step_runs_execution", "step_runs", ["execution_id"])
    op.create_index("ix_step_runs_attempt_open", "step_runs", ["execution_attempt_id", "status"])

    op.create_table(
        "attempt_pauses",
        sa.Column("execution_attempt_id", sa.String(80), sa.ForeignKey("execution_attempts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("start_sequence", sa.Integer(), primary_key=True),
        sa.Column("reason", sa.String(40), nullable=False),
        sa.Column("item_key", sa.String(120), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "estimate_snapshots",
        sa.Column("execution_attempt_id", sa.String(80), sa.ForeignKey("execution_attempts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("entry_key", sa.String(250), primary_key=True),  # "<item>|<etapa>"
        sa.Column("execution_id", sa.String(80), sa.ForeignKey("orchestration_executions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_execution_id", sa.String(80), sa.ForeignKey("task_executions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cutoff", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_agora()),
    )
    op.create_index("ix_estimate_snapshots_execution", "estimate_snapshots", ["execution_id"])

    # -- Dispatch: token do job e comandos do modo direto ---------------------------------
    op.create_table(
        "job_tokens",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("task_execution_id", sa.String(80), sa.ForeignKey("task_executions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("execution_attempt_id", sa.String(80), sa.ForeignKey("execution_attempts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("direct_instance_id", sa.String(80), sa.ForeignKey("direct_instances.id"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_agora()),
        sa.UniqueConstraint("token_hash", name="uq_job_tokens_hash"),
    )
    op.create_index("ix_job_tokens_attempt", "job_tokens", ["execution_attempt_id"])

    op.create_table(
        "direct_commands",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("execution_attempt_id", sa.String(80), sa.ForeignKey("execution_attempts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("command", JSONB, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pendente"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_agora()),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_direct_commands_attempt_status", "direct_commands", ["execution_attempt_id", "status"])


def downgrade() -> None:
    op.drop_table("direct_commands")
    op.drop_table("job_tokens")
    op.drop_table("estimate_snapshots")
    op.drop_table("attempt_pauses")
    op.drop_table("step_runs")
    op.drop_column("execution_events", "executor_id")
    op.drop_column("execution_events", "executor_type")
    op.drop_table("step_plans")
    op.drop_table("execution_items")
    op.drop_index("ix_execution_attempts_executor", table_name="execution_attempts")
    op.drop_index("ix_execution_attempts_machine", table_name="execution_attempts")
    op.drop_constraint("ck_execution_attempts_executor", "execution_attempts", type_="check")
    op.drop_column("execution_attempts", "machine_id")
    op.drop_column("execution_attempts", "executor_id")
    op.drop_column("execution_attempts", "executor_type")
    op.drop_table("direct_instances")
    op.drop_index("ix_agents_machine_id", table_name="agents")
    op.drop_column("agents", "machine_id")
    op.drop_table("machines")
    # agent_id e agent_instance_id continuam anuláveis: voltar a NOT NULL falharia se já
    # houver tentativas do modo direto, e apagá-las perderia histórico.
