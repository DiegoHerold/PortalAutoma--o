from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Execution(BaseModel):
    __tablename__ = "executions"

    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False)
    worker_id: Mapped[int | None] = mapped_column(ForeignKey("workers.id"))
    execution_status: Mapped[str] = mapped_column(Text, default="pending", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_summary: Mapped[str | None] = mapped_column(Text())
    result_payload_json: Mapped[dict | None] = mapped_column(JSONB)

    job = relationship("Job", back_populates="executions")
    worker = relationship("Worker", back_populates="executions")
    logs = relationship("ExecutionLog", back_populates="execution")
