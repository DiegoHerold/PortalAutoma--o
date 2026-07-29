from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

VALID_CONDITIONS = {"success", "failed", "always"}


class TriggerCreateRequest(BaseModel):
    automation_id: int
    trigger_type: str = "https"
    route_path: str | None = None
    secret_token: str | None = None
    is_active: bool = True
    parameter_mapping_json: dict[str, str] | None = None
    template: str | None = None
    source_automation_id: int | None = None
    condition: str | None = None

    @model_validator(mode="after")
    def check_type_specific_fields(self) -> "TriggerCreateRequest":
        if self.trigger_type == "https":
            if not self.route_path or not self.secret_token:
                raise ValueError("route_path e secret_token sao obrigatorios para trigger_type='https'.")
        elif self.trigger_type == "chained":
            if not self.source_automation_id:
                raise ValueError("source_automation_id e obrigatorio para trigger_type='chained'.")
            if self.condition not in VALID_CONDITIONS:
                raise ValueError(f"condition deve ser um de: {', '.join(sorted(VALID_CONDITIONS))}.")
            if self.source_automation_id == self.automation_id:
                raise ValueError("Uma automacao nao pode encadear para si mesma.")
        else:
            raise ValueError("trigger_type deve ser 'https' ou 'chained'.")
        return self


class TriggerUpdateRequest(TriggerCreateRequest):
    pass


class TriggerResponse(TriggerCreateRequest):
    id: int

    class Config:
        from_attributes = True


class TriggerDryRunRequest(BaseModel):
    sample_payload: dict = Field(default_factory=dict)
    sample_headers: dict[str, str] = Field(default_factory=dict)
    sample_query_params: dict[str, str] = Field(default_factory=dict)


class TriggerDryRunResponse(BaseModel):
    automation_id: int
    parameters: dict
    valid: bool = True
    errors: list[str] = Field(default_factory=list)
