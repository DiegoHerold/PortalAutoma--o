from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database import Base


class OutboxMessageRecord(Base):
    __tablename__ = "outbox_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    topic: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    message_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    aggregate_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    aggregate_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    correlation_id: Mapped[str | None] = mapped_column(String(120), index=True)
    causation_id: Mapped[str | None] = mapped_column(String(120), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)


class InboxMessageRecord(Base):
    __tablename__ = "inbox_messages"

    message_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    source: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    source_id: Mapped[str | None] = mapped_column(String(120), index=True)
    message_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text)


class ExecutionEventRecord(Base):
    __tablename__ = "execution_events"
    __table_args__ = (
        UniqueConstraint("execution_attempt_id", "event_sequence", name="uq_execution_events_attempt_sequence"),
        Index("ix_execution_events_execution_received", "execution_id", "received_at"),
        Index("ix_execution_events_task_received", "task_execution_id", "received_at"),
        Index("ix_execution_events_attempt_sequence", "execution_attempt_id", "event_sequence"),
        Index("ix_execution_events_agent_received", "agent_id", "received_at"),
        Index("ix_execution_events_type_received", "event_type", "received_at"),
        Index("ix_execution_events_level_received", "level", "received_at"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    execution_id: Mapped[str] = mapped_column(ForeignKey("orchestration_executions.id", ondelete="CASCADE"), nullable=False, index=True)
    task_execution_id: Mapped[str] = mapped_column(ForeignKey("task_executions.id", ondelete="CASCADE"), nullable=False, index=True)
    execution_attempt_id: Mapped[str] = mapped_column(ForeignKey("execution_attempts.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id"), nullable=True, index=True)
    agent_instance_id: Mapped[str | None] = mapped_column(ForeignKey("agent_instances.id"), nullable=True, index=True)
    executor_type: Mapped[str] = mapped_column(String(20), nullable=False, default="agent", server_default="agent")
    executor_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    event_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    level: Mapped[str | None] = mapped_column(String(20), index=True)
    message: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    message_id: Mapped[str | None] = mapped_column(String(120), index=True)
    correlation_id: Mapped[str | None] = mapped_column(String(120), index=True)
    causation_id: Mapped[str | None] = mapped_column(String(120), index=True)


class EventAcknowledgementRecord(Base):
    __tablename__ = "event_acknowledgements"

    execution_attempt_id: Mapped[str] = mapped_column(ForeignKey("execution_attempts.id", ondelete="CASCADE"), primary_key=True)
    highest_received_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    highest_contiguous_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    missing_ranges: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    duplicate_sequences: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ExecutionMetricRecord(Base):
    __tablename__ = "execution_metrics"
    __table_args__ = (
        UniqueConstraint("execution_attempt_id", "event_sequence", "metric_name", name="uq_execution_metrics_attempt_sequence_name"),
        Index("ix_execution_metrics_execution_received", "execution_id", "received_at"),
        Index("ix_execution_metrics_attempt_name_received", "execution_attempt_id", "metric_name", "received_at"),
        Index("ix_execution_metrics_name_received", "metric_name", "received_at"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("execution_events.id", ondelete="CASCADE"), nullable=False, index=True)
    execution_id: Mapped[str] = mapped_column(ForeignKey("orchestration_executions.id", ondelete="CASCADE"), nullable=False, index=True)
    task_execution_id: Mapped[str] = mapped_column(ForeignKey("task_executions.id", ondelete="CASCADE"), nullable=False, index=True)
    execution_attempt_id: Mapped[str] = mapped_column(ForeignKey("execution_attempts.id", ondelete="CASCADE"), nullable=False, index=True)
    event_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    metric_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    metric_type: Mapped[str] = mapped_column(String(40), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(40))
    labels: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)


class StepRunRecord(Base):
    """Uma etapa medida numa tentativa: a base das estimativas."""

    __tablename__ = "step_runs"
    __table_args__ = (
        UniqueConstraint("execution_attempt_id", "start_sequence", name="uq_step_runs_attempt_sequence"),
        Index("ix_step_runs_history", "automation_id", "step_key", "item_key", "completed_at"),
        Index("ix_step_runs_attempt_open", "execution_attempt_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    execution_id: Mapped[str] = mapped_column(ForeignKey("orchestration_executions.id", ondelete="CASCADE"), nullable=False, index=True)
    task_execution_id: Mapped[str] = mapped_column(ForeignKey("task_executions.id", ondelete="CASCADE"), nullable=False)
    execution_attempt_id: Mapped[str] = mapped_column(ForeignKey("execution_attempts.id", ondelete="CASCADE"), nullable=False)
    automation_id: Mapped[int] = mapped_column(Integer, nullable=False)
    automation_version_id: Mapped[int] = mapped_column(Integer, nullable=False)
    step_key: Mapped[str] = mapped_column(String(120), nullable=False)
    item_key: Mapped[str | None] = mapped_column(String(120))
    work_signature: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="executando")
    planned_tasks: Mapped[int | None] = mapped_column(Integer)
    tasks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    gross_seconds: Mapped[float | None] = mapped_column(Float)
    paused_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    net_seconds: Mapped[float | None] = mapped_column(Float)
    machine_id: Mapped[str | None] = mapped_column(String(80))
    executor_type: Mapped[str] = mapped_column(String(20), nullable=False, default="agent")
    start_sequence: Mapped[int] = mapped_column(Integer, nullable=False)


class AttemptPauseRecord(Base):
    """Tempo fora do controle da automação (reinício, espera externa)."""

    __tablename__ = "attempt_pauses"

    execution_attempt_id: Mapped[str] = mapped_column(ForeignKey("execution_attempts.id", ondelete="CASCADE"), primary_key=True)
    start_sequence: Mapped[int] = mapped_column(Integer, primary_key=True)
    reason: Mapped[str] = mapped_column(String(40), nullable=False)
    item_key: Mapped[str | None] = mapped_column(String(120))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EstimateSnapshotRecord(Base):
    """Estimativa congelada no início (regra 8): uma linha por item e etapa da tentativa."""

    __tablename__ = "estimate_snapshots"

    execution_attempt_id: Mapped[str] = mapped_column(ForeignKey("execution_attempts.id", ondelete="CASCADE"), primary_key=True)
    entry_key: Mapped[str] = mapped_column(String(250), primary_key=True)
    execution_id: Mapped[str] = mapped_column(ForeignKey("orchestration_executions.id", ondelete="CASCADE"), nullable=False, index=True)
    task_execution_id: Mapped[str] = mapped_column(ForeignKey("task_executions.id", ondelete="CASCADE"), nullable=False)
    cutoff: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class StepImageRecord(Base):
    """Imagem de um passo (Fase 4): três medidas no Storage, nunca no banco."""

    __tablename__ = "step_images"
    __table_args__ = (
        UniqueConstraint("execution_attempt_id", "imagem_id", name="uq_step_images_tentativa_imagem"),
        Index("ix_step_images_execution", "execution_id", "created_at"),
        Index("ix_step_images_automacao_criada", "automation_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    imagem_id: Mapped[str] = mapped_column(String(80), nullable=False)
    execution_id: Mapped[str] = mapped_column(ForeignKey("orchestration_executions.id", ondelete="CASCADE"), nullable=False)
    task_execution_id: Mapped[str] = mapped_column(ForeignKey("task_executions.id", ondelete="CASCADE"), nullable=False)
    execution_attempt_id: Mapped[str] = mapped_column(ForeignKey("execution_attempts.id", ondelete="CASCADE"), nullable=False)
    automation_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    origem: Mapped[str] = mapped_column(String(20), nullable=False)
    cheia_id: Mapped[str | None] = mapped_column(ForeignKey("stored_objects.id"), nullable=True)
    media_id: Mapped[str | None] = mapped_column(ForeignKey("stored_objects.id"), nullable=True)
    miniatura_id: Mapped[str | None] = mapped_column(ForeignKey("stored_objects.id"), nullable=True)
    largura: Mapped[int | None] = mapped_column(Integer, nullable=True)
    altura: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    motivo_recusa: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    apagada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class NotificationPreferenceRecord(Base):
    """O que cada pessoa quer receber (Fase 6). Sem linha: nada."""

    __tablename__ = "notification_preferences"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    tipos: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    fila_minutos: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class NotificationRecord(Base):
    """Ocorrência agregada: a chave única impede repetir a mesma."""

    __tablename__ = "notifications"
    __table_args__ = (UniqueConstraint("chave", name="uq_notifications_chave"),)

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    chave: Mapped[str] = mapped_column(String(300), nullable=False)
    tipos: Mapped[list] = mapped_column(JSONB, nullable=False)
    titulo: Mapped[str] = mapped_column(String(300), nullable=False)
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    link: Mapped[str | None] = mapped_column(String(300), nullable=True)
    automation_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    execution_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    quando: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class NotificationDeliveryRecord(Base):
    """Um aviso por endereço e ocorrência; lido no portal e, quando ligado, enviado por e-mail."""

    __tablename__ = "notification_deliveries"
    __table_args__ = (
        UniqueConstraint("notification_id", "email", name="uq_notification_deliveries_endereco"),
        Index("ix_notification_deliveries_usuario", "user_id", "created_at"),
        Index("ix_notification_deliveries_envio", "email_status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    notification_id: Mapped[str] = mapped_column(ForeignKey("notifications.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    email_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pendente")
    tentativas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ultimo_erro: Mapped[str | None] = mapped_column(String(500), nullable=True)
    enviado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
