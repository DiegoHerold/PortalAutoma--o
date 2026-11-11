"""Fase 4: concessões por automação, imagens dos passos e a Central de telas.

Aditiva.

- ``automation_grants`` (Access): quem pode o quê em cada automação, por usuário ou por
  time. Ações: ``ver_execucoes``, ``ver_telas_e_logs``, ``editar_itens``, ``executar``,
  ``controlar`` (decisão 6).
- ``step_images`` (Telemetry): a imagem de cada passo, nas três medidas (miniatura,
  média e cheia), guardada no Storage. Nunca em banco nem em URL pública.
- Permissão global ``central_de_telas`` (só administradores, por padrão).

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e3f4a5b6c7d8"
down_revision = "d2e3f4a5b6c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "automation_grants",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("automation_id", sa.Integer(), sa.ForeignKey("automations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("access_teams.id", ondelete="CASCADE"), nullable=True),
        sa.Column("acoes", postgresql.JSONB(), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("(user_id IS NULL) <> (team_id IS NULL)", name="ck_automation_grants_um_destinatario"),
    )
    op.create_index("ix_automation_grants_automation", "automation_grants", ["automation_id"])
    op.create_index("uq_automation_grants_usuario", "automation_grants", ["automation_id", "user_id"], unique=True,
                    postgresql_where=sa.text("user_id IS NOT NULL"))
    op.create_index("uq_automation_grants_time", "automation_grants", ["automation_id", "team_id"], unique=True,
                    postgresql_where=sa.text("team_id IS NOT NULL"))

    op.create_table(
        "step_images",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("imagem_id", sa.String(80), nullable=False),
        sa.Column("execution_id", sa.String(80), sa.ForeignKey("orchestration_executions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_execution_id", sa.String(80), sa.ForeignKey("task_executions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("execution_attempt_id", sa.String(80), sa.ForeignKey("execution_attempts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("automation_id", sa.Integer(), nullable=True),
        sa.Column("origem", sa.String(20), nullable=False),
        sa.Column("cheia_id", sa.String(36), sa.ForeignKey("stored_objects.id"), nullable=True),
        sa.Column("media_id", sa.String(36), sa.ForeignKey("stored_objects.id"), nullable=True),
        sa.Column("miniatura_id", sa.String(36), sa.ForeignKey("stored_objects.id"), nullable=True),
        sa.Column("largura", sa.Integer(), nullable=True),
        sa.Column("altura", sa.Integer(), nullable=True),
        sa.Column("bytes", sa.Integer(), nullable=True),
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("motivo_recusa", sa.String(300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("execution_attempt_id", "imagem_id", name="uq_step_images_tentativa_imagem"),
    )
    op.create_index("ix_step_images_execution", "step_images", ["execution_id", "created_at"])

    op.execute("INSERT INTO permissions (key, description) VALUES ('central_de_telas', "
               "'Ver as telas e os logs de todas as máquinas ao vivo (Central de telas)') ON CONFLICT (key) DO NOTHING")


def downgrade() -> None:
    op.execute("DELETE FROM permissions WHERE key = 'central_de_telas'")
    op.drop_index("ix_step_images_execution", table_name="step_images")
    op.drop_table("step_images")
    op.drop_index("uq_automation_grants_time", table_name="automation_grants")
    op.drop_index("uq_automation_grants_usuario", table_name="automation_grants")
    op.drop_index("ix_automation_grants_automation", table_name="automation_grants")
    op.drop_table("automation_grants")
