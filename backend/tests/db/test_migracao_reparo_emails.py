"""Migration c8b9c0d1e2f4 (13/11/2026): no banco em que a c6e7f8a9b0c2 foi pulada (número repetido),
as tabelas de e-mail aparecem; num banco novo, nada muda. Banco próprio e descartável."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from tests.db.test_migracao_contas_de_servico import _alembic

NOME = "portal_testes_migracao_reparo_emails"


def test_reparo_cria_as_tabelas_de_email_que_faltam() -> None:
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

    def tabelas() -> set[str]:
        with motor.connect() as c:
            return {t for (t,) in c.execute(text("SELECT table_name FROM information_schema.tables WHERE table_name LIKE 'email%'"))}

    try:
        _alembic("upgrade", "head", banco=NOME)  # banco novo: a c6 cria, o reparo não faz nada
        assert tabelas() == {"emails", "email_anexos", "email_dominios"}
        _alembic("downgrade", "c7f8a9b0c1d3", banco=NOME)
        with motor.begin() as c:  # o estado do banco do Portal: número aplicado, tabelas ausentes
            c.execute(text("DROP TABLE email_anexos; DROP TABLE emails; DROP TABLE email_dominios"))
        assert tabelas() == set()
        _alembic("upgrade", "head", banco=NOME)
        assert tabelas() == {"emails", "email_anexos", "email_dominios"}
        with motor.connect() as c:
            indices = {i for (i,) in c.execute(text("SELECT indexname FROM pg_indexes WHERE tablename = 'emails'"))}
        assert {"ix_emails_criado_em", "ix_emails_situacao_proxima"} <= indices
    finally:
        motor.dispose()
        admin.execute(f"DROP DATABASE IF EXISTS {NOME} WITH (FORCE)")
        admin.close()
