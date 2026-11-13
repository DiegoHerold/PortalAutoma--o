"""E-mail centralizado (13/11/2026): validação, domínios permitidos, tentativas e o registro das notificações."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest

from modules.telemetry.application.use_cases.notificacoes import ErroDeEnvio
from modules.telemetry.correio.correio import (
    MAXIMO_DE_TENTATIVAS,
    CarteiroQueRegistra,
    Contexto,
    Correio,
    EmailInvalido,
    validar,
)

AGORA = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)


class Repo:
    def __init__(self) -> None:
        self.registros: list[Any] = []
        self._dominios: list[str] = []
        self.anexos_guardados: dict[str, list] = {}

    def dominios(self) -> list[str]:
        return list(self._dominios)

    def adicionar_dominio(self, d: str, por: Any, agora: Any) -> None:
        self._dominios.append(d)

    def criar(self, *, id, contexto, mensagem, meio, situacao, motivo, chave, agora, guardar_anexos, nomes_dos_anexos=None):
        r = SimpleNamespace(id=id, contexto=contexto, mensagem=mensagem, meio=meio, situacao=situacao, motivo=motivo,
                            chave_idempotencia=chave, tentativas=0, proxima_tentativa_em=None, enviado_em=None)
        self.anexos_guardados[id] = list(mensagem.anexos) if guardar_anexos else []
        self.registros.append(r)
        return r

    def marcar(self, r, *, situacao=None, tentativas=None, motivo="_", proxima="_", enviado_em=None):
        if situacao is not None:
            r.situacao = situacao
        if tentativas is not None:
            r.tentativas = tentativas
        if motivo != "_":
            r.motivo = motivo
        if proxima != "_":
            r.proxima_tentativa_em = proxima
        if enviado_em is not None:
            r.enviado_em = enviado_em

    def por_chave(self, execucao, chave):
        return next((r for r in self.registros if r.contexto.execution_id == execucao and r.chave_idempotencia == chave), None)

    def apagar_conteudo_dos_anexos(self, r):
        self.anexos_guardados[r.id] = []

    def na_fila(self, agora, limite):
        return [r for r in self.registros if r.situacao == "na_fila" and (r.proxima_tentativa_em is None or r.proxima_tentativa_em <= agora)]

    def mensagem(self, r):
        return r.mensagem


class Carteiro:
    def __init__(self) -> None:
        self.enviados: list[dict] = []
        self.falhar: ErroDeEnvio | None = None

    def enviar(self, para, assunto, texto, **extra) -> None:
        if self.falhar is not None:
            raise self.falhar
        self.enviados.append({"para": para, "assunto": assunto, **extra})


def _automacao() -> Contexto:
    return Contexto(origem="automacao", automation_id=7, execution_id="exe_1", job_id="tsk_1", instancia_id="dri_1")


def test_validar_corrige_e_recusa() -> None:
    m = validar({"para": "Ana@Biason.NET; ana@biason.net, joao@cliente.com.br", "assunto": "  Folha \n 10/2026 ",
                 "html": "<p>oi</p>"}, [("C:\\pasta\\resultado.xlsx", "", b"x" * 10)])
    assert m.para == ["Ana@biason.net", "joao@cliente.com.br"] and m.assunto == "Folha 10/2026"
    assert m.anexos == [("resultado.xlsx", "application/octet-stream", b"x" * 10)]
    for dados, anexos, erro in [
        ({"assunto": "a", "html": "b"}, [], "destinatário"),
        ({"para": "x@", "assunto": "a", "html": "b"}, [], "inválido"),
        ({"para": "a@b.com", "html": "b"}, [], "assunto"),
        ({"para": "a@b.com", "assunto": "a"}, [], "corpo"),
        ({"para": "a@b.com", "assunto": "a", "html": "b"}, [("virus.exe", "", b"1")], "não permitido"),
        ({"para": "a@b.com", "assunto": "a", "html": "b"}, [("grande.pdf", "", b"1" * (3 * 1024 * 1024))], "2,5 MB"),
    ]:
        with pytest.raises(EmailInvalido, match=erro):
            validar(dados, anexos)


def test_dominios_recusa_registrada_e_idempotencia() -> None:
    repo, carteiro = Repo(), Carteiro()
    correio = Correio(repo, carteiro, "portal@biason.net", agora=lambda: AGORA)
    assert correio.permitido("ana@biason.net") and correio.permitido("ana@folha.biason.net")  # o do remetente sempre pode
    assert not correio.permitido("joao@cliente.com.br") and not correio.permitido("x@biason.net.evil.com")
    m = validar({"para": ["joao@cliente.com.br"], "cc": ["ana@biason.net"], "assunto": "a", "html": "b"})
    recusado = correio.pedir(_automacao(), m)
    assert recusado.situacao == "recusado" and "cliente.com.br" in recusado.motivo and carteiro.enviados == []
    correio.adicionar_dominio("Cliente.com.br", "1")
    enviado = correio.pedir(_automacao(), m, chave_idempotencia="folha-101")
    assert enviado.situacao == "enviado" and len(carteiro.enviados) == 1 and carteiro.enviados[0]["cc"] == ["ana@biason.net"]
    assert correio.pedir(_automacao(), m, chave_idempotencia="folha-101") is enviado and len(carteiro.enviados) == 1
    # O próprio Portal (notificação, login) não passa pela lista de domínios.
    assert correio.pedir(Contexto(origem="portal", tipo="teste"), validar({"para": "x@gmail.com", "assunto": "a", "html": "b"})).situacao == "enviado"


def test_temporario_tenta_de_novo_e_definitivo_falha() -> None:
    repo, carteiro = Repo(), Carteiro()
    agora = [AGORA]
    correio = Correio(repo, carteiro, "portal@biason.net", agora=lambda: agora[0])
    m = validar({"para": "ana@biason.net", "assunto": "a", "html": "b"}, [("r.csv", "text/csv", b"1;2")])
    carteiro.falhar = ErroDeEnvio("HTTP 503", temporario=True)
    r = correio.pedir(_automacao(), m)
    assert r.situacao == "na_fila" and r.proxima_tentativa_em == AGORA + timedelta(minutes=1) and repo.anexos_guardados[r.id]
    assert correio.enviar_pendentes() == {"enviados": 0, "falhas": 0, "na_fila": 0}  # ainda não deu a hora
    agora[0] = AGORA + timedelta(minutes=2)
    carteiro.falhar = None
    assert correio.enviar_pendentes()["enviados"] == 1 and r.situacao == "enviado" and repo.anexos_guardados[r.id] == []
    carteiro.falhar = ErroDeEnvio("HTTP 503", temporario=True)
    outro = correio.pedir(_automacao(), m)
    for _ in range(MAXIMO_DE_TENTATIVAS):
        agora[0] += timedelta(hours=2)
        correio.enviar_pendentes()
    assert outro.situacao == "falhou" and outro.tentativas == MAXIMO_DE_TENTATIVAS
    carteiro.falhar = ErroDeEnvio("HTTP 400, ErrorInvalidRecipients", temporario=False)
    definitivo = correio.pedir(_automacao(), m)
    assert definitivo.situacao == "falhou" and definitivo.tentativas == 1 and "400" in definitivo.motivo


def test_desligado_fica_na_fila_e_maquina_so_registra() -> None:
    repo = Repo()
    correio = Correio(repo, None, "", agora=lambda: AGORA)
    r = correio.pedir(Contexto(origem="portal"), validar({"para": "ana@biason.net", "assunto": "a", "texto": "b"}))
    assert r.situacao == "na_fila" and "desligado" in r.motivo
    maquina = correio.registrar_da_maquina(_automacao(), {"para": ["joao@cliente.com.br"], "assunto": "Folha", "meio": "outlook",
                                                         "anexos": ["a.pdf"], "enviado_em": "2026-11-13T11:00:00Z"})
    assert maquina.situacao == "enviado_pela_maquina" and maquina.meio == "outlook" and maquina.contexto.origem == "maquina"
    with pytest.raises(EmailInvalido, match="meio"):
        correio.registrar_da_maquina(_automacao(), {"para": ["a@b.com"], "assunto": "x", "meio": "pombo"})


def test_notificacoes_tambem_ficam_registradas() -> None:
    repo, carteiro = Repo(), Carteiro()
    registrando = CarteiroQueRegistra(carteiro, repo, agora=lambda: AGORA)
    registrando.enviar("gestor@biason.net", "Máquina offline", "MAQ10 sem sinal")
    assert [r.situacao for r in repo.registros] == ["enviado"] and repo.registros[0].contexto.tipo == "notificacao"
    carteiro.falhar = ErroDeEnvio("HTTP 503", temporario=True)
    with pytest.raises(ErroDeEnvio):
        registrando.enviar("gestor@biason.net", "Fila parada", "texto")
    assert repo.registros[-1].situacao == "falhou"
