"""Fase 3: fila, trava de tela por máquina nos dois modos e job perdido.

Aditiva. A trava de tela usa ``resource_locks`` (índice único ativo por escopo e chave),
agora também sem Agent (modo direto) e com a máquina.

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d2e3f4a5b6c7"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None

ATIVOS = "status IN ('queued', 'ready', 'running')"


def upgrade() -> None:
    op.add_column("task_executions", sa.Column("group_key", sa.String(120), nullable=True))
    op.add_column("task_executions", sa.Column("dedup_key", sa.String(64), nullable=True))
    op.add_column("task_executions", sa.Column("manual_position", sa.Integer(), nullable=True))
    op.add_column("task_executions", sa.Column("enqueue_batch_id", sa.String(80), nullable=True))
    op.add_column("task_executions", sa.Column("enqueued_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("task_executions", sa.Column("pool", sa.String(20), nullable=True))
    op.add_column("task_executions", sa.Column("required_machine_id", sa.String(80), sa.ForeignKey("machines.id"), nullable=True))
    op.add_column("task_executions", sa.Column("lost_at", sa.DateTime(timezone=True), nullable=True))
    # Mesmo pedido já na fila ou rodando aponta para o job existente (cenário 4), inclusive
    # com dois pedidos chegando ao mesmo tempo.
    op.create_index("uq_task_executions_dedup_active", "task_executions", ["dedup_key"], unique=True,
                    postgresql_where=sa.text(f"dedup_key IS NOT NULL AND {ATIVOS}"))
    op.create_index("ix_task_executions_queue", "task_executions", ["status", "enqueue_batch_id"])

    op.alter_column("resource_locks", "agent_id", existing_type=sa.String(80), nullable=True)
    op.add_column("resource_locks", sa.Column("machine_id", sa.String(80), sa.ForeignKey("machines.id"), nullable=True))
    op.create_index("ix_resource_locks_machine", "resource_locks", ["machine_id"])

    op.add_column("machines", sa.Column("pool_capacity", postgresql.JSONB(astext_type=sa.Text()), nullable=False,
                                        server_default=sa.text("""'{"interactive": 1, "browser": 1, "background": 2}'::jsonb""")))
    op.add_column("direct_instances", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("direct_instances", "last_seen_at")
    op.drop_column("machines", "pool_capacity")
    op.drop_index("ix_resource_locks_machine", table_name="resource_locks")
    op.drop_column("resource_locks", "machine_id")
    op.drop_index("ix_task_executions_queue", table_name="task_executions")
    op.drop_index("uq_task_executions_dedup_active", table_name="task_executions")
    for coluna in ("lost_at", "required_machine_id", "pool", "enqueued_at", "enqueue_batch_id", "manual_position",
                   "dedup_key", "group_key"):
        op.drop_column("task_executions", coluna)
