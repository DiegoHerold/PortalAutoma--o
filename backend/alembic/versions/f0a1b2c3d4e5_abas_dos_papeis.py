"""Abas de cada papel (12/11/2026).

Aditiva. ``roles.abas`` (Access): as abas do menu que o papel vê. Nulo = todas (é como os
papéis estavam antes), então nada muda para quem já usa o Portal.

Revision ID: f0a1b2c3d4e5
Revises: e9f0a1b2c3d4
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f0a1b2c3d4e5"
down_revision = "e9f0a1b2c3d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("roles", sa.Column("abas", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("roles", "abas")
