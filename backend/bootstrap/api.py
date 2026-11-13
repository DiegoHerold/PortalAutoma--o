from __future__ import annotations

from pathlib import Path
from typing import Any

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import APIRouter, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from api import health
from api.errors import http_error, install_error_handlers
from gateway.bootstrap import router as agent_gateway_router
from gateway.direct_gateway import router as direct_gateway_router
from infrastructure.config import get_settings
from infrastructure.database import SessionLocal
from infrastructure.logging import configure_logging
from infrastructure.orm_metadata import initialize_orm_metadata
from modules.access.api.routes import router as access_module_router
from modules.catalog.api.github_integrations import router as github_integrations_router
from modules.catalog.api.imports import router as automation_imports_router
from modules.catalog.api.routes import router as catalog_module_router
from modules.dispatch.api.routes import router as dispatch_module_router
from gateway.direct_gateway.instancias import router as instancias_diretas_router
from modules.access.api.concessoes import router as concessoes_router
from modules.access.api.acesso_da_pessoa import router as acesso_da_pessoa_router
from modules.access.api.papeis import router as papeis_router
from modules.access.api.contas_de_servico import router as contas_de_servico_router
from modules.access.api.times import router as times_router
from modules.fleet.api.instancias_diretas import router as admin_instancias_router
from modules.dispatch.api.fila import router as fila_router
from modules.fleet.api.routes import router as fleet_module_router
from modules.governance.api.routes import router as governance_module_router
from modules.orchestration.api.job_compat import router as job_compat_router
from modules.orchestration.api.routes import router as orchestration_module_router
from modules.orchestration.flows.api.routes import router as flow_module_router
from modules.orchestration.scheduling.api.routes import (
    router as schedule_module_router,
    schedule_executions_router as schedule_executions_module_router,
)
from modules.orchestration.triggers.api.routes import router as trigger_module_router
from modules.orchestration.triggers.api.webhooks import router as webhook_module_router
from modules.storage.api.routes import router as storage_module_router
from modules.storage.api.arquivos_da_automacao import router as arquivos_da_automacao_router
from modules.telemetry.api.acompanhar import router as acompanhar_router
from modules.telemetry.api.painel import router as painel_router
from modules.catalog.api.itens import router as itens_router
from modules.catalog.api.formulario import router as formulario_router
from modules.telemetry.api.notificacoes import router as notificacoes_router
from modules.governance.api.retencao import router as retencao_router
from modules.governance.api.auditoria import router as auditoria_router
from modules.governance.api.segredos import router as segredos_router
from modules.governance.api import registro_de_requisicoes
from modules.telemetry.api.realtime import router as realtime_router
from modules.telemetry.api.routes import automation_times_router as telemetry_times_router
from modules.telemetry.api.routes import router as telemetry_module_router
from bootstrap.defaults import BootstrapService


def create_api_application() -> FastAPI:
    settings = get_settings()
    configure_logging()
    initialize_orm_metadata()

    app = FastAPI(title=settings.app_name)
    install_error_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("x-content-type-options", "nosniff")
        response.headers.setdefault("x-frame-options", "DENY")
        response.headers.setdefault("referrer-policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("content-security-policy", "default-src 'self'; frame-ancestors 'none'")
        if settings.environment == "production":
            response.headers.setdefault("strict-transport-security", "max-age=31536000; includeSubDomains")
        return response

    # Toda alteração feita por uma pessoa vai para a auditoria (12/11/2026).
    registro_de_requisicoes.instalar(app, settings.api_v1_prefix)

    api_router = APIRouter()
    register_access_routes(api_router)
    register_catalog_routes(api_router)
    register_fleet_routes(api_router)
    register_execution_routes(api_router)
    register_flow_routes(api_router)
    register_schedule_routes(api_router)
    register_governance_routes(api_router)
    register_compatibility_routes(api_router)
    api_router.include_router(health.router, prefix="/health", tags=["health"])
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.on_event("startup")
    def on_startup() -> None:
        with SessionLocal() as db:
            BootstrapService(db).ensure_defaults()

    @app.get("/")
    def root() -> dict[str, str]:
        return {"message": settings.app_name}

    @app.get("/health")
    def healthcheck() -> dict[str, str]:
        return {"status": "ok", "app": settings.app_name}

    @app.get("/api/health")
    def agent_base_health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    def readiness() -> dict[str, Any]:
        checks = _readiness_checks(settings.environment)
        if not all(item["ok"] for item in checks.values()):
            raise http_error(status.HTTP_503_SERVICE_UNAVAILABLE, "DEPENDENCY_UNAVAILABLE", "API is not ready.", checks)
        return {"status": "ready", "checks": checks}

    return app


def register_access_routes(router: APIRouter) -> None:
    router.include_router(access_module_router, tags=["access"])


def register_catalog_routes(router: APIRouter) -> None:
    router.include_router(catalog_module_router, tags=["catalog"])


def register_fleet_routes(router: APIRouter) -> None:
    router.include_router(fleet_module_router, tags=["fleet"])
    router.include_router(agent_gateway_router)
    router.include_router(direct_gateway_router)


def register_execution_routes(router: APIRouter) -> None:
    router.include_router(orchestration_module_router, tags=["orchestration"])
    router.include_router(job_compat_router, tags=["jobs"])
    router.include_router(trigger_module_router, tags=["triggers"])
    router.include_router(webhook_module_router, tags=["webhooks"])
    router.include_router(dispatch_module_router, tags=["dispatch"])
    router.include_router(fila_router)
    router.include_router(concessoes_router)
    router.include_router(times_router)
    router.include_router(papeis_router)
    router.include_router(contas_de_servico_router)
    router.include_router(acesso_da_pessoa_router)
    router.include_router(instancias_diretas_router)
    router.include_router(admin_instancias_router)
    router.include_router(telemetry_module_router, tags=["telemetry"])
    router.include_router(acompanhar_router)
    router.include_router(painel_router)
    router.include_router(itens_router)
    router.include_router(formulario_router)
    router.include_router(notificacoes_router)
    router.include_router(telemetry_times_router, tags=["telemetry"])
    router.include_router(storage_module_router, tags=["storage"])
    router.include_router(arquivos_da_automacao_router)


def register_flow_routes(router: APIRouter) -> None:
    router.include_router(flow_module_router, tags=["flows"])


def register_schedule_routes(router: APIRouter) -> None:
    router.include_router(schedule_module_router, prefix="/schedules", tags=["schedules"])
    router.include_router(schedule_executions_module_router, prefix="/schedule-executions", tags=["schedules"])


def register_governance_routes(router: APIRouter) -> None:
    router.include_router(governance_module_router, tags=["governance"])
    router.include_router(retencao_router)
    router.include_router(auditoria_router)
    router.include_router(segredos_router)


def register_compatibility_routes(router: APIRouter) -> None:
    router.include_router(automation_imports_router, prefix="/automations", tags=["automation-imports"])
    router.include_router(github_integrations_router, prefix="/integrations/github", tags=["github-integration"])
    router.include_router(realtime_router, prefix="/ws", tags=["realtime"])


def _readiness_checks(environment: str) -> dict[str, dict[str, Any]]:
    checks: dict[str, dict[str, Any]] = {}
    with SessionLocal() as db:
        try:
            db.execute(text("select 1")).scalar_one()
            checks["postgresql"] = {"ok": True}
        except Exception as exc:
            checks["postgresql"] = {"ok": False, "detail": str(exc)}
        checks["migrations"] = _migration_check(db)
    settings = get_settings()
    checks["encryption_key"] = {
        "ok": environment != "production" or bool(settings.governance_local_encryption_key),
        "detail": "required in production",
    }
    return checks


def _migration_check(db) -> dict[str, Any]:
    try:
        current = db.execute(text("select version_num from alembic_version limit 1")).scalar_one_or_none()
        alembic_cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        heads = ScriptDirectory.from_config(alembic_cfg).get_heads()
        return {"ok": bool(current and current in heads), "current": current, "heads": heads}
    except Exception as exc:
        return {"ok": False, "detail": str(exc)}
