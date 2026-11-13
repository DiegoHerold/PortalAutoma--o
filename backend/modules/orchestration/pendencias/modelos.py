"""Pendências e os avisos com "Continuar processo" (13/11/2026). Só o Orchestration escreve aqui."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database import Base


class PendenciaRecord(Base):
    __tablename__ = "pendencias"
    __table_args__ = (UniqueConstraint("execution_id", "item_key", name="uq_pendencias_execucao_item"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    execution_id: Mapped[str] = mapped_column(ForeignKey("orchestration_executions.id", ondelete="CASCADE"), nullable=False)
    automation_id: Mapped[int] = mapped_column(ForeignKey("automations.id", ondelete="CASCADE"), nullable=False)
    item_key: Mapped[str] = mapped_column(String(120), nullable=False)
    rotulo: Mapped[str | None] = mapped_column(String(200))
    motivo: Mapped[str | None] = mapped_column(Text)
    situacao: Mapped[str] = mapped_column(String(20), nullable=False, default="aguardando")
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    resolvida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolvida_por: Mapped[str | None] = mapped_column(String(120))
    resolvida_via: Mapped[str | None] = mapped_column(String(20))
    continuacao_execution_id: Mapped[str | None] = mapped_column(String(80))


class PendenciaAvisoRecord(Base):
    __tablename__ = "pendencia_avisos"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    execution_id: Mapped[str] = mapped_column(ForeignKey("orchestration_executions.id", ondelete="CASCADE"), nullable=False, index=True)
    automation_id: Mapped[int] = mapped_column(ForeignKey("automations.id", ondelete="CASCADE"), nullable=False)
    item_keys: Mapped[list] = mapped_column(JSONB, nullable=False)
    destinatarios: Mapped[list] = mapped_column(JSONB, nullable=False)
    origem: Mapped[str] = mapped_column(String(20), nullable=False)
    email_id: Mapped[str | None] = mapped_column(String(40))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
