"""E-mail centralizado no Portal (13/11/2026).

- ``emails``: todo e-mail que o Portal envia (das automações e do próprio Portal) e os que a
  automação avisa que mandou pela máquina. Situação: na_fila, enviado, falhou, recusado,
  enviado_pela_maquina. Tentativas e próxima tentativa para o reenvio automático.
- ``email_anexos``: nome, tipo e tamanho; o conteúdo só até o envio (depois fica nulo).
- ``email_dominios``: para quais domínios as automações podem mandar (o domínio do remetente
  sempre pode).

Revision ID: c6e7f8a9b0c2
Revises: c5d6e7f8a9b1
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "c6e7f8a9b0c2"
down_revision = "c5d6e7f8a9b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "emails",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("origem", sa.String(20), nullable=False),  # automacao | portal | maquina
        sa.Column("tipo", sa.String(40), nullable=False, server_default="mensagem"),
        sa.Column("automation_id", sa.Integer(), sa.ForeignKey("automations.id", ondelete="SET NULL")),
        sa.Column("execution_id", sa.String(80)),
        sa.Column("job_id", sa.String(80)),
        sa.Column("instancia_id", sa.String(80)),
        sa.Column("criado_por", sa.String(120)),
        sa.Column("para", JSONB(), nullable=False),
        sa.Column("cc", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("cco", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("assunto", sa.String(255), nullable=False),
        sa.Column("html", sa.Text()),
        sa.Column("texto", sa.Text()),
        sa.Column("situacao", sa.String(30), nullable=False),
        sa.Column("motivo", sa.String(500)),
        sa.Column("meio", sa.String(20), nullable=False, server_default="graph"),
        sa.Column("tentativas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("proxima_tentativa_em", sa.DateTime(timezone=True)),
        sa.Column("chave_idempotencia", sa.String(120)),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("enviado_em", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_emails_criado_em", "emails", ["criado_em"])
    op.create_index("ix_emails_situacao_proxima", "emails", ["situacao", "proxima_tentativa_em"])
    op.create_index("ix_emails_execucao", "emails", ["execution_id"])
    op.create_index("ix_emails_automacao", "emails", ["automation_id"])
    op.create_table(
        "email_anexos",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("email_id", sa.String(40), sa.ForeignKey("emails.id", ondelete="CASCADE"), nullable=False),
        sa.Column("nome", sa.String(160), nullable=False),
        sa.Column("tipo", sa.String(120), nullable=False),
        sa.Column("tamanho", sa.Integer(), nullable=False),
        sa.Column("conteudo", sa.LargeBinary()),
    )
    op.create_index("ix_email_anexos_email", "email_anexos", ["email_id"])
    op.create_table(
        "email_dominios",
        sa.Column("dominio", sa.String(255), primary_key=True),
        sa.Column("criado_por", sa.String(120)),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("email_dominios")
    op.drop_index("ix_email_anexos_email", table_name="email_anexos")
    op.drop_table("email_anexos")
    for indice in ("ix_emails_automacao", "ix_emails_execucao", "ix_emails_situacao_proxima", "ix_emails_criado_em"):
        op.drop_index(indice, table_name="emails")
    op.drop_table("emails")
