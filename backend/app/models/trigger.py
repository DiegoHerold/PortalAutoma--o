from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Trigger(BaseModel):
    __tablename__ = "triggers"

    automation_id: Mapped[int] = mapped_column(ForeignKey("automations.id"), nullable=False)
    # "webhook" | "chained"
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False)
    route_path: Mapped[str] = mapped_column(String(255), nullable=False)
    secret_token: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Dot-path mapping from the incoming payload (webhook body, or the source
    # automation's result for "chained") to this automation's declared
    # inputs, e.g. {"cliente_id": "body.cliente.id"}. Empty/null means "pass
    # the whole payload through as a single parameter" (legacy behavior).
    parameter_mapping_json: Mapped[dict | None] = mapped_column(JSONB)

    # Purely a UI affordance: which preset the mapping editor was started
    # from (generico | email | arquivo | sistema_externo). Not used for any
    # backend logic.
    template: Mapped[str | None] = mapped_column(String(50))

    # Only set when trigger_type == "chained".
    source_automation_id: Mapped[int | None] = mapped_column(ForeignKey("automations.id"), nullable=True)
    condition: Mapped[str | None] = mapped_column(String(20))  # success | failed | always

    automation = relationship("Automation", back_populates="triggers", foreign_keys=[automation_id])
    source_automation = relationship("Automation", foreign_keys=[source_automation_id])
