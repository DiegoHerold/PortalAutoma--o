"""Times com permissões por categoria, e máquinas que podem ser apagadas do cadastro.

Aditiva.
- ``access_team_category_permissions`` (Access): ver e executar por categoria, dadas a um time;
  quem é membro de um time ativo ganha.
- ``machines.removida_em`` (Fleet): a máquina apagada sai das telas e do despacho, mas o registro
  fica para o histórico das execuções que rodaram nela. O nome deixa de ser único entre as
  apagadas: uma máquina nova pode usar o nome de uma que saiu.

Revision ID: e9f0a1b2c3d4
Revises: d8e9f0a1b2c3
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e9f0a1b2c3d4"
down_revision = "d8e9f0a1b2c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "access_team_category_permissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("access_teams.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("can_view", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("can_execute", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("team_id", "category_id", name="uq_team_category_permissions"),
    )
    op.add_column("machines", sa.Column("removida_em", sa.DateTime(timezone=True), nullable=True))
    op.drop_constraint("uq_machines_name", "machines", type_="unique")
    op.create_index("uq_machines_name_em_uso", "machines", ["name"], unique=True,
                    postgresql_where=sa.text("status <> 'removida'"))


def downgrade() -> None:
    op.drop_index("uq_machines_name_em_uso", table_name="machines")
    op.create_unique_constraint("uq_machines_name", "machines", ["name"])
    op.drop_column("machines", "removida_em")
    op.drop_table("access_team_category_permissions")
