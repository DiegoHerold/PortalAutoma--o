"""Automação externa: roda instalada na máquina dela e fala com o Portal pelo SDK (modo direto).
Publica sem pacote nem runtime do Portal; as outras continuam exigindo os dois."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from modules.catalog.application.dto import ActorDTO
from modules.catalog.application.use_cases.versions import PublishAutomationVersion
from modules.catalog.domain.errors import CatalogValidationError
from modules.catalog.domain.manifest import ENTRYPOINT_EXTERNA, parse_automation_manifest

MANIFESTO = {
    "schema_version": "1.0",
    "automation": {"id": "dominio.integracao_contabil", "name": "Integração Contábil", "version": "0.1.0"},
    "runtime": {"id": "python-desktop", "version": "3.12"},
    "entrypoint": {"type": "externa", "comando": "dfolha central trabalhar"},
    "execution": {"mode": "tela"},
    "etapas": [{"chave": "iniciar", "nome": "Iniciar", "por_item": False},
               {"chave": "rubricas", "nome": "Rubricas", "por_tarefa": True}],
}


def test_manifesto_externo_e_valido() -> None:
    manifesto, resultado = parse_automation_manifest(json.dumps(MANIFESTO))
    assert resultado.is_valid, resultado.errors
    assert manifesto.entrypoint_type == ENTRYPOINT_EXTERNA == "externa"
    assert manifesto.normalized["entrypoint"]["type"] == "externa"


class _Catalogo:
    def __init__(self, versao) -> None:
        self.versao = versao
        self.atualizacoes: list[tuple[int, dict]] = []
        self.pacotes: list[str] = []

    def get_automation(self, _id):
        return SimpleNamespace(id=1, status="active", is_active=True)

    def get_version_for_automation(self, _a, _v):
        return self.versao

    def get_package(self, _id):
        return None

    def find_runtime_version(self, *_):
        return None

    def get_runtime_version(self, _id):
        return None

    def get_latest_published_version(self, _a):
        return None

    def update_version(self, version_id, campos):
        self.atualizacoes.append((version_id, campos))
        return SimpleNamespace(**{**vars(self.versao), **campos})

    def update_package(self, package_id, _campos):
        self.pacotes.append(package_id)


class _Nada:
    def __getattr__(self, _nome):
        return lambda *a, **k: None


def _publicar(versao):
    catalogo = _Catalogo(versao)
    publicada = PublishAutomationVersion(catalogo, _Nada(), _Nada(), _Nada()).execute(
        1, versao.id, ActorDTO(actor_type="user", actor_id="1", actor_email="adm@teste.invalid"))
    return publicada, catalogo


def _versao(tipo: str, **extra):
    base = dict(id=10, status="draft", manifest_id="man_1", package_id=None, entrypoint_type=tipo,
                runtime_id="python-desktop", runtime_version="3.12", runtime_version_id=None, version="0.1.0")
    return SimpleNamespace(**{**base, **extra})


def test_externa_publica_sem_pacote_nem_runtime() -> None:
    publicada, catalogo = _publicar(_versao("externa"))
    assert publicada.status == "published"
    assert catalogo.atualizacoes == [(10, {"status": "published", "runtime_version_id": None, "published_by": "1"})]
    assert catalogo.pacotes == []


@pytest.mark.parametrize("tipo", ["python-module", "executable"])
def test_as_outras_continuam_exigindo_pacote(tipo: str) -> None:
    with pytest.raises(CatalogValidationError, match="package"):
        _publicar(_versao(tipo))
