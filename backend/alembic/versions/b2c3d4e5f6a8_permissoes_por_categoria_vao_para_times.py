"""As permissões por categoria saem da pessoa e vão para times (12/11/2026).

- ``access_team_category_permissions`` ganha ``can_create``, ``can_edit``, ``can_delete`` e
  ``can_approve`` (as mesmas que a pessoa tinha).
- Dados: cada conjunto de permissões de quem não é admin vira um time "Acessos de <nome>" com
  essas pessoas, e as permissões soltas saem delas (``migracao_para_times.migrar``). Ninguém ganha
  nem perde acesso. O downgrade tira as colunas, mas não devolve as permissões às pessoas.

Revision ID: b2c3d4e5f6a8
Revises: a1b2c3d4e5f7
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b2c3d4e5f6a8"
down_revision = "a1b2c3d4e5f7"
branch_labels = None
depends_on = None

NOVAS = ("can_create", "can_edit", "can_delete", "can_approve")


def upgrade() -> None:
    for coluna in NOVAS:
        op.add_column("access_team_category_permissions",
                      sa.Column(coluna, sa.Boolean(), nullable=False, server_default=sa.false()))
    from modules.access.infrastructure.repositories.migracao_para_times import migrar

    migrar(op.get_bind())


def downgrade() -> None:
    for coluna in NOVAS:
        op.drop_column("access_team_category_permissions", coluna)
