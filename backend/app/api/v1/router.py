from fastapi import APIRouter

from app.api.v1.endpoints import (
    audit,
    auth,
    automations,
    categories,
    executions,
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

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(categories.router, prefix="/categories", tags=["categories"])
api_router.include_router(automations.router, prefix="/automations", tags=["automations"])
api_router.include_router(triggers.router, prefix="/triggers", tags=["triggers"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(executions.router, prefix="/executions", tags=["executions"])
api_router.include_router(workers.router, prefix="/workers", tags=["workers"])
api_router.include_router(schedules.router, prefix="/schedules", tags=["schedules"])
api_router.include_router(roles.router, prefix="/roles", tags=["roles"])
api_router.include_router(audit.router, prefix="/audit", tags=["audit"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(realtime.router, prefix="/ws", tags=["realtime"])
api_router.include_router(health.router, prefix="/health", tags=["health"])
