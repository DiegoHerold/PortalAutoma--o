from fastapi import APIRouter

from app.api.v1.endpoints import (
    audit,
    agents,
    auth,
    automation_imports,
    automations,
    categories,
    executions,
    github_integrations,
    health,
    jobs,
    realtime,
    roles,
    schedules,
    triggers,
    users,
    webhooks,
    workers,
)
from modules.catalog.api.routes import router as catalog_module_router
from modules.fleet.api.routes import router as fleet_module_router
from modules.orchestration.api.routes import router as orchestration_module_router
from gateway.bootstrap import router as agent_gateway_router

api_router = APIRouter()
api_router.include_router(agents.router, tags=["agents"])
api_router.include_router(fleet_module_router, tags=["fleet"])
api_router.include_router(agent_gateway_router)
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(categories.router, prefix="/categories", tags=["categories"])
api_router.include_router(automations.router, prefix="/automations", tags=["automations"])
api_router.include_router(automation_imports.router, prefix="/automations", tags=["automation-imports"])
api_router.include_router(catalog_module_router, tags=["catalog"])
api_router.include_router(orchestration_module_router, tags=["orchestration"])
api_router.include_router(triggers.router, prefix="/triggers", tags=["triggers"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(executions.router, prefix="/executions", tags=["executions"])
api_router.include_router(workers.router, prefix="/workers", tags=["workers"])
api_router.include_router(schedules.router, prefix="/schedules", tags=["schedules"])
api_router.include_router(roles.router, prefix="/roles", tags=["roles"])
api_router.include_router(audit.router, prefix="/audit", tags=["audit"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(
    github_integrations.router, prefix="/integrations/github", tags=["github-integration"]
)
api_router.include_router(realtime.router, prefix="/ws", tags=["realtime"])
api_router.include_router(health.router, prefix="/health", tags=["health"])
