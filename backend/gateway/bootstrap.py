from __future__ import annotations

from fastapi import APIRouter

from gateway.agent_gateway.endpoint import router as agent_gateway_router

router = APIRouter()
router.include_router(agent_gateway_router, tags=["agent-gateway"])
