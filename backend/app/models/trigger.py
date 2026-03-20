from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Trigger(BaseModel):
    __tablename__ = "triggers"

    automation_id: Mapped[int] = mapped_column(ForeignKey("automations.id"), nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False)
    route_path: Mapped[str] = mapped_column(String(255), nullable=False)
    secret_token: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    automation = relationship("Automation", back_populates="triggers")
