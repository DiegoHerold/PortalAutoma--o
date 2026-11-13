"""Migrations c4d5e6f7a8b0 (segredos com campos) e c5d6e7f8a9b1 (webhooks novos) com dados de antes.

Banco próprio e descartável (não o compartilhado, nunca o real). Um segredo de um valor só vira o
campo ``valor``; um webhook antigo vira webhook novo desligado e sem token; o gatilho em cadeia
não vira webhook; a tabela ``triggers`` não muda. Desce e sobe de novo sem erro.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from tests.db.test_migracao_contas_de_servico import _alembic

NOME = "portal_testes_migracao_webhooks"


def test_segredo_e_webhooks_de_antes() -> None:
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
        _alembic("upgrade", "c3d4e5f6a7b9", banco=NOME)
        with motor.begin() as c:
            c.execute(text("INSERT INTO secrets (id, key, name, status) VALUES ('sec_antigo', 'erp.token', 'Token', 'active')"))
            categoria = c.execute(text("INSERT INTO categories (name, slug, is_active) VALUES ('Folha', 'folha', true) RETURNING id")).scalar()
            automacao = c.execute(text(
                "INSERT INTO automations (name, slug, category_id, executor_type, default_priority, timeout_seconds, max_retries,"
                " is_active, status) VALUES ('IC', 'ic', :c, 'agent', 'normal', 3600, 0, true, 'active') RETURNING id"),
                {"c": categoria}).scalar()
            c.execute(text("INSERT INTO triggers (name, automation_id, trigger_type, route_path, secret_token, is_active) VALUES "
                           "('ERP antigo', :a, 'generic', 'erp/folha', 'segredo-antigo', true), "
                           "('Cadeia', :a, 'chained', 'cadeia', 'x', true)"), {"a": automacao})
        _alembic("upgrade", "c5d6e7f8a9b1", banco=NOME)
        with motor.connect() as c:
            assert c.execute(text("SELECT campos FROM secrets WHERE id = 'sec_antigo'")).scalar() == [{"nome": "valor", "oculto": True}]
            webhooks = c.execute(text("SELECT nome, ativo, token_hash, token_final, automation_id FROM webhooks")).all()
            assert len(webhooks) == 1  # o gatilho em cadeia não vira webhook
            w = webhooks[0]
            assert (w.nome, w.ativo, w.token_final, w.automation_id) == ("ERP antigo", False, None, automacao)
            assert w.token_hash.startswith("!sem-token!")  # nunca autentica
            assert c.execute(text("SELECT count(*) FROM triggers WHERE is_active")).scalar() == 2  # triggers não muda
        _alembic("downgrade", "c3d4e5f6a7b9", banco=NOME)
        with motor.connect() as c:
            assert c.execute(text("SELECT to_regclass('webhooks')")).scalar() is None
            assert c.execute(text("SELECT count(*) FROM triggers")).scalar() == 2
        _alembic("upgrade", "head", banco=NOME)
    finally:
        motor.dispose()
        admin.execute(f"DROP DATABASE IF EXISTS {NOME} WITH (FORCE)")
        admin.close()
