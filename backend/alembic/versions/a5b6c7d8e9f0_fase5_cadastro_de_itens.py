"""Fase 5: cadastro de itens por automação (decisão 1; seção 6.5 da Fase 0).

Aditiva. ``automation_items`` (Catalog): chave, nome, grupo de um nível (matriz e
filiais), atributos validados pelo schema do manifesto e ativo, com quem alterou.

Revision ID: a5b6c7d8e9f0
Revises: f4a5b6c7d8e9
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a5b6c7d8e9f0"
down_revision = "f4a5b6c7d8e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "automation_items",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("automation_id", sa.Integer(), sa.ForeignKey("automations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chave", sa.String(120), nullable=False),
        sa.Column("rotulo", sa.String(255), nullable=False),
        sa.Column("grupo_chave", sa.String(120), nullable=True),
        sa.Column("atributos", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(120), nullable=True),
        sa.Column("updated_by", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("automation_id", "chave", name="uq_automation_items_chave"),
    )
    op.create_index("ix_automation_items_grupo", "automation_items", ["automation_id", "grupo_chave"])


def downgrade() -> None:
    op.drop_index("ix_automation_items_grupo", table_name="automation_items")
    op.drop_table("automation_items")
