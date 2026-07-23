from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class GithubIntegration(BaseModel):
    """
    One installed GitHub App instance (an account or organization that installed
    the Biason Automations GitHub App). Only installation_id is stored; access
    tokens are short-lived and fetched on demand from GitHub, never persisted.
    """

    __tablename__ = "github_integrations"

    installation_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    account_login: Mapped[str] = mapped_column(String(200), nullable=False)
    account_type: Mapped[str] = mapped_column(String(30), nullable=False)  # "User" | "Organization"
    connected_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    sources = relationship("AutomationSource", back_populates="integration")
