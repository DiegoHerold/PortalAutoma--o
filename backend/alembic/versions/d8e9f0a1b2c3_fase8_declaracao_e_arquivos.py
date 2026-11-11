"""Fase 8: a automação se declara ao conectar, e os arquivos que ela entrega.

Aditiva.
- ``automation_forms.item``: o que é um item da automação (nome, chave, grupo), quando vem da
  declaração e não do manifesto.
- ``automation_item_proposals`` (Catalog): a tabela de itens que a automação mandou, à espera
  de alguém aprovar na aba Itens (uma por automação, a mais recente).
- ``automation_retention.arquivos_dias``: prazo dos arquivos entregues (sem prazo, nada sai).

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d8e9f0a1b2c3"
down_revision = "c7d8e9f0a1b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("automation_forms", sa.Column("item", postgresql.JSONB(), nullable=True))
    op.create_table(
        "automation_item_proposals",
        sa.Column("automation_id", sa.Integer(), sa.ForeignKey("automations.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("linhas", postgresql.JSONB(), nullable=False),
        sa.Column("resumo", postgresql.JSONB(), nullable=False),
        sa.Column("instancia_id", sa.String(80), nullable=True),
        sa.Column("recebida_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.add_column("automation_retention", sa.Column("arquivos_dias", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("automation_retention", "arquivos_dias")
    op.drop_table("automation_item_proposals")
    op.drop_column("automation_forms", "item")
