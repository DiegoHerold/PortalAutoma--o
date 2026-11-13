"""Segredos com vários campos (13/11/2026).

``secrets.campos``: a lista de campos do segredo, ``[{"nome": "usuario", "oculto": false},
{"nome": "senha", "oculto": true}]``. Os valores continuam cifrados juntos, na versão
(``secret_versions.encrypted_value`` passa a ser o JSON ``{"v": 2, "campos": {...}}`` cifrado).

Dados: os segredos de antes (um valor só) ficam com ``[{"nome": "valor", "oculto": true}]``; o
valor cifrado antigo continua legível (texto puro cifrado = campo ``valor``), sem recifrar.

Revision ID: c4d5e6f7a8b0
Revises: c3d4e5f6a7b9
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "c4d5e6f7a8b0"
down_revision = "c3d4e5f6a7b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("secrets", sa.Column("campos", JSONB(), nullable=True))
    op.execute("""UPDATE secrets SET campos = '[{"nome": "valor", "oculto": true}]'::jsonb WHERE campos IS NULL""")


def downgrade() -> None:
    op.drop_column("secrets", "campos")
