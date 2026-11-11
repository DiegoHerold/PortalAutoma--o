"""Modo direto: inscrição com código de uso único, chave pública, desafio e sessão.

Antecipado da Fase 6 para ligar a Integração Contábil (pedido de 10/11/2026). Desenho da
seção 7 da Fase 0: o administrador gera um código de uso único; a instância se inscreve
com a chave pública ECDSA P-256 (a privada fica na máquina, protegida pelo DPAPI); fica
pendente até o administrador aprovar e escolher a máquina; cada sessão de 10 minutos sai
de um desafio assinado. Só hashes de códigos e tokens são guardados.

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f4a5b6c7d8e9"
down_revision = "e3f4a5b6c7d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "direct_enrollment_codes",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("automation_id", sa.Integer(), sa.ForeignKey("automations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_by", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("direct_instance_id", sa.String(80), sa.ForeignKey("direct_instances.id"), nullable=True),
    )
    op.add_column("direct_instances", sa.Column("public_key", sa.Text(), nullable=True))
    op.add_column("direct_instances", sa.Column("quarantined_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "direct_challenges",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("direct_instance_id", sa.String(80), sa.ForeignKey("direct_instances.id", ondelete="CASCADE"), nullable=False),
        sa.Column("nonce", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_direct_challenges_instance", "direct_challenges", ["direct_instance_id"])
    op.create_table(
        "direct_sessions",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("direct_instance_id", sa.String(80), sa.ForeignKey("direct_instances.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_direct_sessions_instance", "direct_sessions", ["direct_instance_id"])


def downgrade() -> None:
    op.drop_index("ix_direct_sessions_instance", table_name="direct_sessions")
    op.drop_table("direct_sessions")
    op.drop_index("ix_direct_challenges_instance", table_name="direct_challenges")
    op.drop_table("direct_challenges")
    op.drop_column("direct_instances", "quarantined_at")
    op.drop_column("direct_instances", "public_key")
    op.drop_table("direct_enrollment_codes")
