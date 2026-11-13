"""Vale para todos os testes do backend (``tests/`` e ``modules/*/tests``).

Nenhum teste grava no armazenamento real do portal. O ``.env`` aponta
``LOCAL_STORAGE_PATH`` para a pasta de dados do portal; alguns testes zeram o cache das
configurações (``get_settings.cache_clear()``) e a instância nova voltaria a ler o ``.env``.
A variável de ambiente vence o ``.env``, então fixá-la aqui, antes de tudo, garante que até
uma instância recriada use a pasta temporária.
"""

from __future__ import annotations

import os
import shutil
import tempfile

_PASTA = tempfile.mkdtemp(prefix="portal_testes_storage_")
os.environ["LOCAL_STORAGE_PATH"] = _PASTA
os.environ["STORAGE_BACKEND"] = "local"
# Nenhum teste manda e-mail de verdade (13/11/2026): o .env tem as credenciais do Graph e o envio
# liga sozinho com elas. Os testes de e-mail usam um carteiro falso injetado.
os.environ["NOTIFICACOES_EMAIL_LIGADO"] = "false"
for _nome in ("GRAPH_TENANT_ID", "GRAPH_CLIENT_ID", "GRAPH_CLIENT_SECRET", "ENTRA_TENANT_ID", "ENTRA_CLIENT_ID", "ENTRA_CLIENT_SECRET"):
    os.environ[_nome] = ""


def pytest_configure(config) -> None:  # noqa: ARG001
    from infrastructure.config import get_settings

    get_settings.cache_clear()


def pytest_unconfigure(config) -> None:  # noqa: ARG001
    shutil.rmtree(_PASTA, ignore_errors=True)
