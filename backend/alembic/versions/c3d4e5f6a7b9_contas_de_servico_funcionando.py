"""Contas de serviço funcionando (13/11/2026).

- ``service_accounts`` ganha ``user_id`` (um usuário técnico com papel e times, como uma
  pessoa, mas sem login por senha), ``description``, ``credential_hint`` (os 4 últimos
  caracteres, para reconhecer a credencial), ``credential_created_at``, ``created_by`` e índice
  em ``credential_hash`` (a credencial é procurada pelo hash SHA-256).
- Dados: as contas de antes nunca autenticaram (a API não aceitava a credencial). Cada uma
  ganha o seu usuário técnico com o papel Viewer, fica **desativada** e sem credencial válida:
  quem for usar gera uma credencial nova e ativa.

Revision ID: c3d4e5f6a7b9
Revises: b2c3d4e5f6a8
"""

from __future__ import annotations

import secrets

import sqlalchemy as sa
from alembic import op

revision = "c3d4e5f6a7b9"
down_revision = "b2c3d4e5f6a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("service_accounts", sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True))
    op.add_column("service_accounts", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("service_accounts", sa.Column("credential_hint", sa.String(16), nullable=True))
    op.add_column("service_accounts", sa.Column("credential_created_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("service_accounts", sa.Column("created_by", sa.String(120), nullable=True))
    op.create_index("uq_service_accounts_user_id", "service_accounts", ["user_id"], unique=True)
    op.create_index("ix_service_accounts_credential_hash", "service_accounts", ["credential_hash"])

    conn = op.get_bind()
    viewer = conn.execute(sa.text("SELECT id FROM roles WHERE slug = 'viewer'")).scalar()
    if viewer is None:
        viewer = conn.execute(sa.text("SELECT id FROM roles ORDER BY id LIMIT 1")).scalar()
    contas = conn.execute(sa.text("SELECT id, name, organization_id FROM service_accounts WHERE user_id IS NULL")).all()
    for conta_id, nome, organizacao in contas:
        if viewer is None:  # banco sem papéis: a conta só fica desativada, sem usuário técnico
            conn.execute(sa.text("UPDATE service_accounts SET status = 'disabled', credential_hash = :h WHERE id = :c"),
                         {"h": f"!sem-credencial!{secrets.token_hex(16)}", "c": conta_id})
            continue
        user_id = conn.execute(sa.text(
            "INSERT INTO users (name, email, password_hash, role_id, organization_id, status, is_active, created_at, updated_at) "
            "VALUES (:n, :e, :p, :r, :o, 'active', true, now(), now()) RETURNING id"),
            {"n": nome, "e": f"{conta_id}@contas-de-servico.invalid", "p": f"!conta-de-servico!{secrets.token_hex(16)}",
             "r": viewer, "o": organizacao}).scalar()
        conn.execute(sa.text(
            "UPDATE service_accounts SET user_id = :u, status = 'disabled', credential_hash = :h, credential_hint = NULL "
            "WHERE id = :c"), {"u": user_id, "h": f"!sem-credencial!{secrets.token_hex(16)}", "c": conta_id})


def downgrade() -> None:
    conn = op.get_bind()
    tecnicos = [u for (u,) in conn.execute(sa.text("SELECT user_id FROM service_accounts WHERE user_id IS NOT NULL")).all()]
    op.drop_index("ix_service_accounts_credential_hash", table_name="service_accounts")
    op.drop_index("uq_service_accounts_user_id", table_name="service_accounts")
    for coluna in ("created_by", "credential_created_at", "credential_hint", "description", "user_id"):
        op.drop_column("service_accounts", coluna)
    if tecnicos:  # só depois de soltar a coluna: o CASCADE apagaria as contas junto
        conn.execute(sa.text("DELETE FROM access_team_memberships WHERE user_id = ANY(:u)"), {"u": tecnicos})
        conn.execute(sa.text("DELETE FROM users WHERE id = ANY(:u)"), {"u": tecnicos})
