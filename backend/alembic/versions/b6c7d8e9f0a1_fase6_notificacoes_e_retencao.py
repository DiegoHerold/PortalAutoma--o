"""Fase 6: notificações e retenção por automação.

Aditiva.
- ``notification_preferences`` (Telemetry): o que cada pessoa quer receber.
- ``notifications``: a ocorrência agregada, com chave única (detectar de novo não repete).
- ``notification_deliveries``: um aviso por endereço e ocorrência (``uq`` garante), lido
  no portal e, quando o envio por e-mail for ligado, enviado pelo Microsoft Graph.
- ``automation_retention`` (Governance): dias de imagens e de logs por automação. Sem
  linha, nada é apagado.
- ``step_images.apagada_em``: a imagem saiu pela retenção (a linha fica, os bytes não).

Revision ID: b6c7d8e9f0a1
Revises: a5b6c7d8e9f0
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b6c7d8e9f0a1"
down_revision = "a5b6c7d8e9f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_preferences",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tipos", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("fila_minutos", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "notifications",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("chave", sa.String(300), nullable=False),
        sa.Column("tipos", postgresql.JSONB(), nullable=False),
        sa.Column("titulo", sa.String(300), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("link", sa.String(300), nullable=True),
        sa.Column("automation_id", sa.Integer(), nullable=True),
        sa.Column("execution_id", sa.String(80), nullable=True),
        sa.Column("quando", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("chave", name="uq_notifications_chave"),
    )
    op.create_index("ix_notifications_created", "notifications", ["created_at"])
    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("notification_id", sa.String(80), sa.ForeignKey("notifications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("email_status", sa.String(20), nullable=False, server_default="pendente"),
        sa.Column("tentativas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ultimo_erro", sa.String(500), nullable=True),
        sa.Column("enviado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lida_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("notification_id", "email", name="uq_notification_deliveries_endereco"),
    )
    op.create_index("ix_notification_deliveries_usuario", "notification_deliveries", ["user_id", "created_at"])
    op.create_index("ix_notification_deliveries_envio", "notification_deliveries", ["email_status", "created_at"])
    op.create_table(
        "automation_retention",
        sa.Column("automation_id", sa.Integer(), sa.ForeignKey("automations.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("imagens_dias", sa.Integer(), nullable=True),
        sa.Column("logs_dias", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.String(120), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.add_column("step_images", sa.Column("apagada_em", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_step_images_automacao_criada", "step_images", ["automation_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_step_images_automacao_criada", table_name="step_images")
    op.drop_column("step_images", "apagada_em")
    op.drop_table("automation_retention")
    op.drop_index("ix_notification_deliveries_envio", table_name="notification_deliveries")
    op.drop_index("ix_notification_deliveries_usuario", table_name="notification_deliveries")
    op.drop_table("notification_deliveries")
    op.drop_index("ix_notifications_created", table_name="notifications")
    op.drop_table("notifications")
    op.drop_table("notification_preferences")
