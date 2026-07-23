from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Automation(BaseModel):
    __tablename__ = "automations"

    name: Mapped[str] = mapped_column(String(180), nullable=False)
    slug: Mapped[str] = mapped_column(String(180), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text())
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    executor_type: Mapped[str] = mapped_column(String(50), nullable=False)
    default_priority: Mapped[str] = mapped_column(String(20), default="normal", nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=300, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    category = relationship("Category", back_populates="automations")
    jobs = relationship("Job", back_populates="automation")
    triggers = relationship("Trigger", back_populates="automation")
    schedules = relationship("Schedule", back_populates="automation")
    worker_preferences = relationship("AutomationWorkerPreference", back_populates="automation")
