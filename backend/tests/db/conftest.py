"""Testes com PostgreSQL de verdade (Fase 2 em diante).

Cria um banco descartável, aplica TODAS as migrations do zero e apaga no fim. Nunca usa
o banco do portal. Sem PostgreSQL acessível, os testes são pulados com o motivo.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

BACKEND = Path(__file__).resolve().parents[2]
NOME = "portal_testes_automaticos"


@pytest.fixture(scope="session")
def engine():
    import psycopg

    from infrastructure.config import get_settings

    s = get_settings()
    try:
        admin = psycopg.connect(host=s.postgres_server, port=s.postgres_port, user=s.postgres_user,
                                password=s.postgres_password, dbname="postgres", autocommit=True, connect_timeout=3)
    except psycopg.OperationalError as exc:
        pytest.skip(f"PostgreSQL indisponível para os testes de banco: {exc}")
    admin.execute(f"DROP DATABASE IF EXISTS {NOME} WITH (FORCE)")
    admin.execute(f"CREATE DATABASE {NOME}")
    migracao = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND,
                              env={**os.environ, "POSTGRES_DB": NOME}, capture_output=True, text=True)
    if migracao.returncode != 0:
        pytest.fail(f"migrations falharam:\n{migracao.stderr[-3000:]}")
    motor = create_engine(f"{s.database_url.rsplit('/', 1)[0]}/{NOME}")
    from modules.telemetry.infrastructure.realtime.postgres import usar_motor

    usar_motor(motor)  # avisos e escuta (LISTEN/NOTIFY) no banco de teste, nunca no real
    yield motor
    usar_motor(None)
    motor.dispose()
    admin.execute(f"DROP DATABASE IF EXISTS {NOME} WITH (FORCE)")
    admin.close()


@pytest.fixture
def sessao(engine) -> Session:
    fabrica = sessionmaker(bind=engine, expire_on_commit=False)
    db = fabrica()
    yield db
    db.rollback()
    db.close()


@pytest.fixture
def cliente(engine, monkeypatch):
    """API real com o banco de teste. O usuário é um administrador (permissões em teste próprio)."""
    from fastapi.testclient import TestClient

    import bootstrap.api as bootstrap_api
    from bootstrap.api import create_api_application
    from infrastructure.database import get_db, get_session_factory
    from modules.access.api.dependencies import get_current_user

    app = create_api_application()
    fabrica = sessionmaker(bind=engine, expire_on_commit=False)
    # A inicialização (papéis, categorias e admin padrão) roda no banco de teste, nunca no real.
    monkeypatch.setattr(bootstrap_api, "SessionLocal", fabrica)

    def _db():
        db = fabrica()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _db
    # Streams e esperas longas abrem sessões curtas pela fábrica: também no banco de teste.
    app.dependency_overrides[get_session_factory] = lambda: fabrica
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, role=SimpleNamespace(slug="admin"))
    with TestClient(app) as c:
        yield c
