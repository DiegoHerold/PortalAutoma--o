from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

VALID_CONDITIONS = {"success", "failed", "always"}


class TriggerBaseRequest(BaseModel):
    name: str | None = None
    automation_id: int
    trigger_type: str = "https"
    route_path: str | None = None
    is_active: bool = True
    parameter_mapping_json: dict[str, str] | None = None
    template: str | None = None
    source_automation_id: int | None = None
    condition: str | None = None

    @model_validator(mode="after")
    def check_type_specific_fields(self) -> "TriggerBaseRequest":
        if self.trigger_type == "https":
            if not self.route_path:
                raise ValueError("route_path e obrigatorio para trigger_type='https'.")
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


class TriggerCreateRequest(TriggerBaseRequest):
    secret_token: str | None = None


class TriggerUpdateRequest(TriggerBaseRequest):
    pass


class TriggerResponse(BaseModel):
    id: int
    name: str | None = None
    automation_id: int
    trigger_type: str
    route_path: str
    is_active: bool
    parameter_mapping_json: dict[str, str] | None = None
    template: str | None = None
    source_automation_id: int | None = None
    condition: str | None = None
    secret_configured: bool
    secret_last_four: str | None = None
    secret_created_at: datetime | None = None
    secret_rotated_at: datetime | None = None
    method: str = "POST"
    required_header: str = "X-Trigger-Secret"
    invocation_url: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_invoked_at: datetime | None = None
    last_execution_id: str | None = None
    last_execution_status: str | None = None
    last_execution_duration_seconds: float | None = None


class TriggerCreateResponse(TriggerResponse):
    secret_token: str | None = None


class TriggerRotateSecretResponse(BaseModel):
    secret_token: str
    created_at: datetime
    previous_secret_revoked: bool = True
    secret_last_four: str


class TriggerDryRunRequest(BaseModel):
    sample_payload: dict = Field(default_factory=dict)
    sample_headers: dict[str, str] = Field(default_factory=dict)
    sample_query_params: dict[str, str] = Field(default_factory=dict)


class TriggerDryRunResponse(BaseModel):
    automation_id: int
    parameters: dict
    valid: bool = True
    errors: list[str] = Field(default_factory=list)
