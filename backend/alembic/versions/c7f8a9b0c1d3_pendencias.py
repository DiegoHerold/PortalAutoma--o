"""Pendências com "Continuar processo" (13/11/2026).

- ``pendencias``: um item que terminou em atenção (precisa de uma pessoa) numa execução. Fica
  ``aguardando`` até alguém continuar (``continuada``: entra uma execução nova só com ele) ou até
  o item rodar de novo por outro caminho (``substituida``). Depois disso, nenhum caminho continua.
- ``pendencia_avisos``: cada e-mail com o botão "Continuar processo" (o link leva ao aviso, no
  Portal, com login). Quem mandou: a automação (no e-mail dela) ou o Portal (para quem pediu).

Revision ID: c7f8a9b0c1d3
Revises: d6e7f8a9b0c2
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "c7f8a9b0c1d3"
down_revision = "d6e7f8a9b0c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pendencias",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("execution_id", sa.String(80), sa.ForeignKey("orchestration_executions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("automation_id", sa.Integer(), sa.ForeignKey("automations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_key", sa.String(120), nullable=False),
        sa.Column("rotulo", sa.String(200)),
        sa.Column("motivo", sa.Text()),
        sa.Column("situacao", sa.String(20), nullable=False, server_default="aguardando"),
        sa.Column("criada_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("resolvida_em", sa.DateTime(timezone=True)),
        sa.Column("resolvida_por", sa.String(120)),
        sa.Column("resolvida_via", sa.String(20)),  # email | portal | outra_execucao
        sa.Column("continuacao_execution_id", sa.String(80)),
        sa.UniqueConstraint("execution_id", "item_key", name="uq_pendencias_execucao_item"),
    )
    op.create_index("ix_pendencias_situacao", "pendencias", ["situacao", "automation_id"])
    op.create_table(
        "pendencia_avisos",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("execution_id", sa.String(80), sa.ForeignKey("orchestration_executions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("automation_id", sa.Integer(), sa.ForeignKey("automations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_keys", JSONB(), nullable=False),
        sa.Column("destinatarios", JSONB(), nullable=False),
        sa.Column("origem", sa.String(20), nullable=False),  # automacao | portal
        sa.Column("email_id", sa.String(40)),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_pendencia_avisos_execucao", "pendencia_avisos", ["execution_id"])


def downgrade() -> None:
    op.drop_index("ix_pendencia_avisos_execucao", table_name="pendencia_avisos")
    op.drop_table("pendencia_avisos")
    op.drop_index("ix_pendencias_situacao", table_name="pendencias")
    op.drop_table("pendencias")
