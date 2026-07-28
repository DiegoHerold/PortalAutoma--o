from fastapi import APIRouter

from app.api.v1.endpoints import (
    automation_imports,
    github_integrations,
    health,
    jobs,
    realtime,
    triggers,
    webhooks,
)
from modules.access.api.routes import router as access_module_router
from modules.catalog.api.routes import router as catalog_module_router
from modules.dispatch.api.routes import router as dispatch_module_router
from modules.fleet.api.routes import router as fleet_module_router
from modules.governance.api.routes import router as governance_module_router
from modules.orchestration.api.routes import router as orchestration_module_router
from modules.orchestration.flows.api.routes import router as flow_module_router
from modules.orchestration.scheduling.api.routes import (
    router as schedule_module_router,
    schedule_executions_router as schedule_executions_module_router,
)
from modules.storage.api.routes import router as storage_module_router
from modules.telemetry.api.routes import router as telemetry_module_router
from gateway.bootstrap import router as agent_gateway_router

api_router = APIRouter()
api_router.include_router(fleet_module_router, tags=["fleet"])
api_router.include_router(agent_gateway_router)
api_router.include_router(access_module_router, tags=["access"])
api_router.include_router(automation_imports.router, prefix="/automations", tags=["automation-imports"])
api_router.include_router(catalog_module_router, tags=["catalog"])
api_router.include_router(orchestration_module_router, tags=["orchestration"])
api_router.include_router(flow_module_router, tags=["flows"])
api_router.include_router(dispatch_module_router, tags=["dispatch"])
api_router.include_router(telemetry_module_router, tags=["telemetry"])
api_router.include_router(storage_module_router, tags=["storage"])
api_router.include_router(governance_module_router, tags=["governance"])
api_router.include_router(triggers.router, prefix="/triggers", tags=["triggers"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(schedule_module_router, prefix="/schedules", tags=["schedules"])
api_router.include_router(schedule_executions_module_router, prefix="/schedule-executions", tags=["schedules"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(
    github_integrations.router, prefix="/integrations/github", tags=["github-integration"]
)
api_router.include_router(realtime.router, prefix="/ws", tags=["realtime"])
api_router.include_router(health.router, prefix="/health", tags=["health"])
