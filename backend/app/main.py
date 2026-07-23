from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.logging import configure_logging
from app.services.bootstrap_service import BootstrapService

settings = get_settings()
configure_logging()

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.on_event("startup")
def on_startup() -> None:
    with SessionLocal() as db:
        BootstrapService(db).ensure_defaults()


@app.get("/")
def root() -> dict[str, str]:
    return {"message": settings.app_name}


@app.get("/api/health")
def agent_base_health() -> dict[str, str]:
    return {"status": "ok"}
