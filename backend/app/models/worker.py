from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Worker(BaseModel):
    __tablename__ = "workers"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    hostname: Mapped[str] = mapped_column(String(120), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    agent_id: Mapped[str | None] = mapped_column(String(80), unique=True, index=True)
    machine_id: Mapped[str | None] = mapped_column(String(120), unique=True, index=True)
    device_token: Mapped[str | None] = mapped_column(Text())
    agent_version: Mapped[str | None] = mapped_column(String(40))
    os: Mapped[str | None] = mapped_column(Text())
    architecture: Mapped[str | None] = mapped_column(String(80))
    capabilities_json: Mapped[list | None] = mapped_column(JSONB)
    last_payload_json: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(30), default="offline", nullable=False)
    max_concurrency: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    jobs = relationship("Job", back_populates="assigned_worker")
    executions = relationship("Execution", back_populates="worker")
    automation_preferences = relationship("AutomationWorkerPreference", back_populates="worker")
