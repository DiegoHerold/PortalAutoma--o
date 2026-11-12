"""Funcionalidades de cada papel (12/11/2026).

Aditiva. ``roles.funcionalidades`` (Access): ``{funcionalidade: "ver"|"gerenciar"}``, a tabela
que o administrador salva na tela Papéis. Nulo = papel de antes: o nível de cada funcionalidade é
deduzido das permissões gravadas (``modules.access.domain.funcionalidades.deduzir``), então
ninguém perde nem ganha acesso com esta migration. ``roles.abas`` (da etapa anterior) fica só
para essa dedução.

Revision ID: a1b2c3d4e5f7
Revises: f0a1b2c3d4e5
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a1b2c3d4e5f7"
down_revision = "f0a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("roles", sa.Column("funcionalidades", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("roles", "funcionalidades")
