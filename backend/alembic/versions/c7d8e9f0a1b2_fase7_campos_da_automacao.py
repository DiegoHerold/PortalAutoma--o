"""Fase 7: campos de cada automação, editáveis no Portal.

Aditiva. ``automation_forms`` (Catalog): a ``entrada`` (o que se informa ao acionar) e as
``colunas`` (o que cada item guarda), com quem mudou. Sem linha, vale o que o manifesto
sugere.

Revision ID: c7d8e9f0a1b2
Revises: b6c7d8e9f0a1
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c7d8e9f0a1b2"
down_revision = "b6c7d8e9f0a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "automation_forms",
        sa.Column("automation_id", sa.Integer(), sa.ForeignKey("automations.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("entrada", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("colunas", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("versao", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_by", sa.String(120), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("automation_forms")
