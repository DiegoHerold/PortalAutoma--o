"""Regras de limpeza do sistema e catálogo de limites (13/11/2026).

- ``regras_de_limpeza``: o prazo de cada regra do catálogo (``governance/domain/configuracoes.py``).
  Sem linha, vale o padrão do catálogo (notificações 7 dias etc.).
- As 10 "políticas por tipo de registro" semeadas antes (``retention_policies``) nunca apagaram
  nada e confundiam com a limpeza real: saem. (O início do Portal as regravava com o padrão a
  cada reinício, então não havia ajuste de ninguém a perder.) A tabela fica, para a API antiga.

Revision ID: d6e7f8a9b0c2
Revises: c6e7f8a9b0c2
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d6e7f8a9b0c2"
down_revision = "c6e7f8a9b0c2"
branch_labels = None
depends_on = None

POLITICAS_SEMEADAS = ("ExecutionEvent", "ExecutionLog", "ExecutionMetric", "Artifact", "AgentResourceSnapshot",
                      "AuditEvent", "InboxMessage", "OutboxMessage", "AgentCommand", "Diagnostic")


def upgrade() -> None:
    op.create_table(
        "regras_de_limpeza",
        sa.Column("chave", sa.String(80), primary_key=True),
        sa.Column("personalizado", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("dias", sa.Integer(), nullable=True),
        sa.Column("atualizado_por", sa.String(120), nullable=True),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ultima_limpeza_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ultima_limpeza_apagados", sa.Integer(), nullable=True),
        sa.Column("total_apagados", sa.Integer(), nullable=False, server_default="0"),
    )
    politicas = sa.table("retention_policies", sa.column("resource_type", sa.String), sa.column("organization_id", sa.Integer))
    op.execute(politicas.delete().where(politicas.c.resource_type.in_(POLITICAS_SEMEADAS),
                                        politicas.c.organization_id.is_(None)))


def downgrade() -> None:
    op.drop_table("regras_de_limpeza")
