from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Schedule(BaseModel):
    __tablename__ = "schedules"

    automation_id: Mapped[int] = mapped_column(ForeignKey("automations.id"), nullable=False)
    cron_expression: Mapped[str] = mapped_column(String(80), nullable=False)
    timezone: Mapped[str] = mapped_column(String(80), nullable=False, default="America/Sao_Paulo")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    automation = relationship("Automation", back_populates="schedules")
