"""Reparo (13/11/2026): cria as tabelas do e-mail centralizado se faltarem.

A migration ``c6e7f8a9b0c2`` (e-mail) teve o mesmo número de uma versão anterior da migration da
limpeza do sistema (hoje ``d6e7f8a9b0c2``). No banco do Portal o número já constava como aplicado,
então ``emails``, ``email_anexos`` e ``email_dominios`` nunca foram criadas e a tela E-mails dava
erro. Aqui elas são criadas só quando não existem: num banco novo (onde a ``c6e7f8a9b0c2`` rodou),
nada muda.

Revision ID: c8b9c0d1e2f4
Revises: c7f8a9b0c1d3
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "c8b9c0d1e2f4"
down_revision = "c7f8a9b0c1d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existe = set(sa.inspect(op.get_bind()).get_table_names())
    if "emails" not in existe:
        op.create_table(
            "emails",
            sa.Column("id", sa.String(40), primary_key=True),
            sa.Column("origem", sa.String(20), nullable=False),
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
    if "email_anexos" not in existe:
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
    if "email_dominios" not in existe:
        op.create_table(
            "email_dominios",
            sa.Column("dominio", sa.String(255), primary_key=True),
            sa.Column("criado_por", sa.String(120)),
            sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )


def downgrade() -> None:
    # Nada: num banco novo as tabelas são da c6e7f8a9b0c2; no reparado, ficam (sem perder e-mails).
    pass
