from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from infrastructure.config import get_settings

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    app: str


@router.get("", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", app=get_settings().app_name)
