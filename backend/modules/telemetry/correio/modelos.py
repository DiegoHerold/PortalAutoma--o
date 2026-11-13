"""Tabelas do e-mail centralizado (13/11/2026). Só o Telemetry (Correio) escreve aqui."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database import Base


class EmailRecord(Base):
    __tablename__ = "emails"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    origem: Mapped[str] = mapped_column(String(20), nullable=False)
    tipo: Mapped[str] = mapped_column(String(40), nullable=False, default="mensagem")
    automation_id: Mapped[int | None] = mapped_column(ForeignKey("automations.id", ondelete="SET NULL"))
    execution_id: Mapped[str | None] = mapped_column(String(80))
    job_id: Mapped[str | None] = mapped_column(String(80))
    instancia_id: Mapped[str | None] = mapped_column(String(80))
    criado_por: Mapped[str | None] = mapped_column(String(120))
    para: Mapped[list] = mapped_column(JSONB, nullable=False)
    cc: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    cco: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    assunto: Mapped[str] = mapped_column(String(255), nullable=False)
    html: Mapped[str | None] = mapped_column(Text)
    texto: Mapped[str | None] = mapped_column(Text)
    situacao: Mapped[str] = mapped_column(String(30), nullable=False)
    motivo: Mapped[str | None] = mapped_column(String(500))
    meio: Mapped[str] = mapped_column(String(20), nullable=False, default="graph")
    tentativas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    proxima_tentativa_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    chave_idempotencia: Mapped[str | None] = mapped_column(String(120))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    enviado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EmailAnexoRecord(Base):
    __tablename__ = "email_anexos"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    email_id: Mapped[str] = mapped_column(ForeignKey("emails.id", ondelete="CASCADE"), nullable=False, index=True)
    nome: Mapped[str] = mapped_column(String(160), nullable=False)
    tipo: Mapped[str] = mapped_column(String(120), nullable=False)
    tamanho: Mapped[int] = mapped_column(Integer, nullable=False)
    conteudo: Mapped[bytes | None] = mapped_column(LargeBinary)


class EmailDominioRecord(Base):
    __tablename__ = "email_dominios"

    dominio: Mapped[str] = mapped_column(String(255), primary_key=True)
    criado_por: Mapped[str | None] = mapped_column(String(120))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
