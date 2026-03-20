from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class ExecutionLog(BaseModel):
    __tablename__ = "execution_logs"

    execution_id: Mapped[int] = mapped_column(ForeignKey("executions.id"), nullable=False)
    level: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(Text(), nullable=False)

    execution = relationship("Execution", back_populates="logs")
