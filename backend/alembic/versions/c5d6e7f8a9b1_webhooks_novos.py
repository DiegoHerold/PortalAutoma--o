"""Webhooks novos (13/11/2026): só acionam uma automação, token no cabeçalho, IPs opcionais.

- ``webhooks``: id público (``whk_...``), automação, nome, ativo, SHA-256 do token e os 4 últimos
  caracteres, IPs/redes permitidos, limite por minuto, último uso.
- ``webhook_chamadas``: cada chamada recebida (aceita, repetida ou recusada, com o motivo), para o
  histórico, o limite por minuto e a chave de idempotência.
- Dados: cada webhook de antes (``triggers`` que não é "em cadeia") vira um webhook novo
  **desligado e sem token** (o token antigo para; gere um novo e ligue). As rotas antigas
  (``/webhooks/trigger/...``, ``/triggers/invoke/...``) respondem 410. Os gatilhos em cadeia
  ficam na tabela ``triggers`` sem uso (nunca tiveram quem os disparasse). A tabela ``triggers``
  não é alterada (o downgrade volta ao que era).

Revision ID: c5d6e7f8a9b1
Revises: c4d5e6f7a8b0
"""

from __future__ import annotations

import secrets

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "c5d6e7f8a9b1"
down_revision = "c4d5e6f7a8b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "webhooks",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("automation_id", sa.Integer(), sa.ForeignKey("automations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("nome", sa.String(180), nullable=False),
        sa.Column("descricao", sa.Text()),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("token_hash", sa.String(120), nullable=False),
        sa.Column("token_final", sa.String(8)),
        sa.Column("token_criado_em", sa.DateTime(timezone=True)),
        sa.Column("ips_permitidos", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("limite_por_minuto", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("criado_por", sa.String(120)),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("ultimo_uso_em", sa.DateTime(timezone=True)),
        sa.Column("legado_trigger_id", sa.Integer()),
    )
    op.create_index("ix_webhooks_automation_id", "webhooks", ["automation_id"])
    op.create_index("ix_webhooks_token_hash", "webhooks", ["token_hash"])
    op.create_table(
        "webhook_chamadas",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("webhook_id", sa.String(40), sa.ForeignKey("webhooks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recebida_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("situacao", sa.String(20), nullable=False),
        sa.Column("motivo", sa.String(300)),
        sa.Column("codigo_http", sa.Integer(), nullable=False),
        sa.Column("ip", sa.String(80)),
        sa.Column("user_agent", sa.String(300)),
        sa.Column("chave_idempotencia", sa.String(120)),
        sa.Column("execution_id", sa.String(80)),
        sa.Column("itens", sa.Integer()),
    )
    op.create_index("ix_webhook_chamadas_webhook_recebida", "webhook_chamadas", ["webhook_id", "recebida_em"])
    op.create_index("ix_webhook_chamadas_idempotencia", "webhook_chamadas", ["webhook_id", "chave_idempotencia"])

    conn = op.get_bind()
    antigos = conn.execute(sa.text(
        "SELECT id, automation_id, name, route_path, created_at FROM triggers "
        "WHERE coalesce(trigger_type, '') <> 'chained' ORDER BY id")).all()
    for trigger_id, automation_id, nome, rota, criado_em in antigos:
        conn.execute(sa.text(
            "INSERT INTO webhooks (id, automation_id, nome, descricao, ativo, token_hash, criado_em, atualizado_em, legado_trigger_id) "
            "VALUES (:i, :a, :n, :d, false, :h, coalesce(:c, now()), now(), :t)"),
            {"i": f"whk_{secrets.token_hex(8)}", "a": automation_id, "n": (nome or f"Webhook {rota}")[:180],
             "d": f"Migrado do webhook antigo /{rota}. Gere um token novo e ligue.", "h": f"!sem-token!{secrets.token_hex(16)}",
             "c": criado_em, "t": trigger_id})


def downgrade() -> None:
    op.drop_index("ix_webhook_chamadas_idempotencia", table_name="webhook_chamadas")
    op.drop_index("ix_webhook_chamadas_webhook_recebida", table_name="webhook_chamadas")
    op.drop_table("webhook_chamadas")
    op.drop_index("ix_webhooks_token_hash", table_name="webhooks")
    op.drop_index("ix_webhooks_automation_id", table_name="webhooks")
    op.drop_table("webhooks")
