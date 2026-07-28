from __future__ import annotations

from fastapi import APIRouter

from gateway.agent_gateway.endpoint import router as agent_gateway_router
from gateway.agent_gateway.http_compat import router as agent_http_compat_router

router = APIRouter()
router.include_router(agent_gateway_router, tags=["agent-gateway"])
router.include_router(agent_http_compat_router, tags=["agent-gateway-compatibility"])
