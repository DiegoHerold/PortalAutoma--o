from sqlalchemy import Boolean, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class AutomationWorkerPreference(BaseModel):
    __tablename__ = "automation_worker_preferences"
    __table_args__ = (
        UniqueConstraint("automation_id", "worker_id", name="uq_automation_worker"),
    )

    automation_id: Mapped[int] = mapped_column(ForeignKey("automations.id"), nullable=False, index=True)
    worker_id: Mapped[int] = mapped_column(ForeignKey("workers.id"), nullable=False)
    priority_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    automation = relationship("Automation", back_populates="worker_preferences")
    worker = relationship("Worker", back_populates="automation_preferences")
