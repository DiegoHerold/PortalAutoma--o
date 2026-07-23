from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class AuditLog(BaseModel):
    __tablename__ = "audit_logs"

    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    actor_email: Mapped[str | None] = mapped_column(String(255), index=True)
    actor_type: Mapped[str | None] = mapped_column(String(50))  # 'user', 'system', 'trigger', 'worker'
    resource_type: Mapped[str | None] = mapped_column(String(80), index=True)
    resource_id: Mapped[str | None] = mapped_column(String(80))
    details: Mapped[str | None] = mapped_column(Text())
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict | None] = mapped_column(JSONB)

