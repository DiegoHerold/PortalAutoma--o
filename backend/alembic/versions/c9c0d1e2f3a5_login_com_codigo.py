"""Login com código por e-mail, navegador confiável, esqueci a senha e convite (13/11/2026).

- ``users.falhas_login`` e ``users.bloqueado_ate``: 10 senhas erradas seguidas travam a conta por
  15 minutos.
- ``acesso_tokens``: tudo o que dá acesso, guardado só como HMAC-SHA256 (nunca em texto):
  ``desafio`` (o passo entre a senha e o código, 15 min), ``codigo`` (6 dígitos, 10 min, 5
  tentativas), ``dispositivo`` (navegador confiável, 30 dias), ``redefinir`` (link de esqueci a
  senha, 1 h, uso único) e ``convite`` (link de criar a senha, 48 h, uso único).

Revision ID: c9c0d1e2f3a5
Revises: c8b9c0d1e2f4
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "c9c0d1e2f3a5"
down_revision = "c8b9c0d1e2f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("falhas_login", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("bloqueado_ate", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "acesso_tokens",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("hash", sa.String(80), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expira_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("usado_em", sa.DateTime(timezone=True)),
        sa.Column("tentativas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("dados", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("ip", sa.String(80)),
    )
    op.create_index("ix_acesso_tokens_hash", "acesso_tokens", ["hash"], unique=True)
    op.create_index("ix_acesso_tokens_usuario_tipo", "acesso_tokens", ["user_id", "tipo"])


def downgrade() -> None:
    op.drop_index("ix_acesso_tokens_usuario_tipo", table_name="acesso_tokens")
    op.drop_index("ix_acesso_tokens_hash", table_name="acesso_tokens")
    op.drop_table("acesso_tokens")
    op.drop_column("users", "bloqueado_ate")
    op.drop_column("users", "falhas_login")
