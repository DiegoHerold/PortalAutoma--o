from pydantic import BaseModel, model_validator

VALID_CONDITIONS = {"success", "failed", "always"}


class TriggerCreate(BaseModel):
    automation_id: int
    trigger_type: str = "https"  # https | chained
    # Required for trigger_type="https"; ignored (auto-generated server-side)
    # for trigger_type="chained", since chaining has no external endpoint.
    route_path: str | None = None
    secret_token: str | None = None
    is_active: bool = True

    parameter_mapping_json: dict[str, str] | None = None  # {parameter_name: "body.some.path"}
    template: str | None = None  # UI preset tag, e.g. "n8n", "generic-post"

    source_automation_id: int | None = None  # required when trigger_type == "chained"
    condition: str | None = None  # success | failed | always -- required when trigger_type == "chained"

    @model_validator(mode="after")
    def _check_type_specific_fields(self) -> "TriggerCreate":
        if self.trigger_type == "https":
            if not self.route_path or not self.secret_token:
                raise ValueError("route_path e secret_token são obrigatórios para trigger_type='https'.")
        elif self.trigger_type == "chained":
            if not self.source_automation_id:
                raise ValueError("source_automation_id é obrigatório para trigger_type='chained'.")
            if self.condition not in VALID_CONDITIONS:
                raise ValueError(f"condition deve ser um de: {', '.join(sorted(VALID_CONDITIONS))}.")
            if self.source_automation_id == self.automation_id:
                raise ValueError("Uma automação não pode encadear para si mesma (source_automation_id == automation_id).")
        else:
            raise ValueError("trigger_type deve ser 'https' ou 'chained'.")
        return self


class TriggerUpdate(TriggerCreate):
    pass


class TriggerRead(TriggerCreate):
    id: int

    class Config:
        from_attributes = True


class TriggerDryRunRequest(BaseModel):
    sample_payload: dict = {}
    sample_headers: dict[str, str] = {}
    sample_query_params: dict[str, str] = {}


class TriggerDryRunResponse(BaseModel):
    automation_id: int
    parameters: dict
    valid: bool = True
    errors: list[str] = []
