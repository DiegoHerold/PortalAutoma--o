"""Migration c3d4e5f6a7b9 com uma conta de serviço de antes (13/11/2026).

Banco próprio e descartável (não o compartilhado dos outros testes, nunca o real): sobe até a
revisão anterior, grava uma conta como o código antigo gravava, sobe a migration e confere; desce
e confere que a conta continua e o usuário técnico sai.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, text

from tests.db.conftest import BACKEND

NOME = "portal_testes_migracao_contas"


def _alembic(*args: str) -> None:
    r = subprocess.run([sys.executable, "-m", "alembic", *args], cwd=BACKEND, env={**os.environ, "POSTGRES_DB": NOME},
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-3000:]


def test_conta_antiga_fica_desativada_com_usuario_tecnico_e_volta_no_downgrade() -> None:
    import psycopg

    from infrastructure.config import get_settings

    s = get_settings()
    try:
        admin = psycopg.connect(host=s.postgres_server, port=s.postgres_port, user=s.postgres_user,
                                password=s.postgres_password, dbname="postgres", autocommit=True, connect_timeout=3)
    except psycopg.OperationalError as exc:
        pytest.skip(f"PostgreSQL indisponível: {exc}")
    admin.execute(f"DROP DATABASE IF EXISTS {NOME} WITH (FORCE)")
    admin.execute(f"CREATE DATABASE {NOME}")
    motor = create_engine(f"{s.database_url.rsplit('/', 1)[0]}/{NOME}")
    try:
        _alembic("upgrade", "b2c3d4e5f6a8")
        with motor.begin() as c:
            c.execute(text("INSERT INTO roles (name, slug) VALUES ('Viewer', 'viewer') ON CONFLICT DO NOTHING"))
            c.execute(text("INSERT INTO service_accounts (id, name, status, credential_hash, permissions) "
                           "VALUES ('sa_antiga', 'Faturamento', 'active', '$2b$12$hashbcryptantigo', '[\"artifact.read\"]')"))
        _alembic("upgrade", "c3d4e5f6a7b9")
        with motor.connect() as c:
            conta = c.execute(text("SELECT status, user_id, credential_hash, credential_hint FROM service_accounts "
                                   "WHERE id = 'sa_antiga'")).one()
            assert conta.status == "disabled" and conta.user_id is not None and conta.credential_hint is None
            assert conta.credential_hash.startswith("!sem-credencial!")  # nunca autentica
            usuario = c.execute(text("SELECT u.name, u.email, u.password_hash, r.slug FROM users u JOIN roles r ON r.id = u.role_id "
                                     "WHERE u.id = :u"), {"u": conta.user_id}).one()
            assert (usuario.name, usuario.email, usuario.slug) == ("Faturamento", "sa_antiga@contas-de-servico.invalid", "viewer")
            assert usuario.password_hash.startswith("!conta-de-servico!")
        _alembic("downgrade", "b2c3d4e5f6a8")
        with motor.connect() as c:
            assert c.execute(text("SELECT name FROM service_accounts WHERE id = 'sa_antiga'")).scalar() == "Faturamento"
            assert c.execute(text("SELECT count(*) FROM users WHERE email LIKE '%@contas-de-servico.invalid'")).scalar() == 0
        _alembic("upgrade", "head")  # e sobe de novo sem erro
    finally:
        motor.dispose()
        admin.execute(f"DROP DATABASE IF EXISTS {NOME} WITH (FORCE)")
        admin.close()
