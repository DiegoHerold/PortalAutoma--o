"""Fase 8: a automação declara o que pede ao conectar e entrega arquivos (planilhas, TXT)."""

from __future__ import annotations

import io
import time
from pathlib import Path

import pytest

from portal_automacoes import Automacao
from portal_automacoes import automacao as modulo_automacao
from portal_automacoes import eventos as ev
from portal_automacoes import instancia as modulo_instancia
from portal_automacoes.fila import FilaLocal
from portal_automacoes.instancia import trabalhar
from portal_automacoes.transporte import FalhaDeTransporte, Recusado
from portal_automacoes.transporte_agente import TransporteAgente
from portal_automacoes.transporte_direto import TransporteDireto
from simuladores.portal_simulado import PortalSimulado

CONTEUDO = "rubrica;valor\n450;10,00\n".encode("utf-8")


@pytest.fixture
def portal():
    with PortalSimulado(None, None, ev.validar) as p:
        p.criar_job("job_a", "token-a")
        yield p


def _automacao(portal: PortalSimulado, tmp_path: Path, segundo_plano: bool = False, log=None) -> Automacao:
    transporte = TransporteDireto(portal.url, "job_a", "token-a", permitir_http=True)
    return Automacao(transporte, FilaLocal(tmp_path / "fila.db"), log_local=log or io.StringIO(),
                     segundo_plano=segundo_plano)


def _arquivo(pasta: Path, nome: str, conteudo: bytes = CONTEUDO) -> Path:
    caminho = pasta / nome
    caminho.write_bytes(conteudo)
    return caminho


# -- arquivos no modo direto --------------------------------------------------------------------
def test_arquivo_vai_ligado_ao_item_atual_com_tipo_e_bytes_exatos(portal: PortalSimulado, tmp_path: Path) -> None:
    txt = _arquivo(tmp_path, "integração 10-2026.txt")
    planilha = _arquivo(tmp_path, "x.xlsx", b"PK\x03\x04")
    with _automacao(portal, tmp_path) as a:
        with a.item("5081", rotulo="Matriz"):
            a.arquivo(txt)
            a.arquivo(planilha, nome="Resumo 5081.xlsx", item=None)  # do lote, não do item
        a.arquivo(str(txt))  # fora de item: sem item
    recebidos = [(x["nome"], x["item"], x["tipo"], x["conteudo"]) for x in portal.jobs["job_a"].arquivos]
    assert recebidos == [
        ("integração 10-2026.txt", "5081", "text/plain", CONTEUDO),
        ("Resumo 5081.xlsx", None, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", b"PK\x03\x04"),
        ("integração 10-2026.txt", None, "text/plain", CONTEUDO),
    ]
    assert portal.recusas_autenticacao == 0  # token no cabeçalho, como nos eventos


def test_arquivo_invalido_falha_na_hora(portal: PortalSimulado, tmp_path: Path, monkeypatch) -> None:
    with _automacao(portal, tmp_path) as a:
        with pytest.raises(FileNotFoundError):
            a.arquivo(tmp_path / "nao-existe.txt")
        with pytest.raises(FileNotFoundError):
            a.arquivo(tmp_path)  # pasta não é arquivo
        with pytest.raises(ValueError, match="vazio"):
            a.arquivo(_arquivo(tmp_path, "vazio.txt", b""))
        monkeypatch.setattr(modulo_automacao, "LIMITE_ARQUIVO", 3)
        with pytest.raises(ValueError, match="100 MB"):
            a.arquivo(_arquivo(tmp_path, "grande.txt", b"1234"))
        assert a.arquivos_pendentes == 0
    assert portal.jobs["job_a"].arquivos == []


def test_portal_fora_do_ar_o_arquivo_espera_e_sai_no_fechar(portal: PortalSimulado, tmp_path: Path) -> None:
    log = io.StringIO()
    portal.fora_do_ar = True
    a = _automacao(portal, tmp_path, log=log)
    a.arquivo(_arquivo(tmp_path, "a.txt"))
    a.arquivo(_arquivo(tmp_path, "b.txt"))
    assert a.arquivos_pendentes == 2 and portal.jobs["job_a"].arquivos == []
    assert "arquivo 'a.txt' não enviado agora" in log.getvalue()
    portal.fora_do_ar = False
    a.fechar()
    assert [x["nome"] for x in portal.jobs["job_a"].arquivos] == ["a.txt", "b.txt"] and a.arquivos_pendentes == 0


def test_o_que_nao_sai_ate_fechar_e_avisado_e_o_arquivo_fica(portal: PortalSimulado, tmp_path: Path) -> None:
    log = io.StringIO()
    portal.fora_do_ar = True
    a = _automacao(portal, tmp_path, log=log)
    caminho = _arquivo(tmp_path, "a.txt")
    a.arquivo(caminho)
    a.fechar(tempo_limite_s=0.6)
    assert f"arquivo 'a.txt' não foi enviado ao Portal (continua em {caminho})" in log.getvalue()
    assert caminho.read_bytes() == CONTEUDO and a.arquivos_pendentes == 0


def test_segundo_plano_quem_entrega_nao_espera_a_rede(portal: PortalSimulado, tmp_path: Path) -> None:
    a = _automacao(portal, tmp_path, segundo_plano=True)
    inicio = time.monotonic()
    for i in range(5):
        a.arquivo(_arquivo(tmp_path, f"{i}.txt"))
    assert time.monotonic() - inicio < 0.5
    limite = time.monotonic() + 5
    while len(portal.jobs["job_a"].arquivos) < 5 and time.monotonic() < limite:
        time.sleep(0.05)
    a.fechar()
    assert [x["nome"] for x in portal.jobs["job_a"].arquivos] == [f"{i}.txt" for i in range(5)]


class _Recusa:
    nome = "direto"
    recusados: list = []

    def __init__(self, erro: Exception) -> None:
        self.erro, self.tentativas = erro, 0

    def conectar(self):
        return 0

    def enviar(self, eventos):
        return max(e["sequence"] for e in eventos)

    def comandos(self):
        return []

    def enviar_imagem(self, imagem_id, jpeg):
        return None

    def enviar_arquivo(self, caminho, nome, item, tipo):
        self.tentativas += 1
        raise self.erro

    def fechar(self):
        return None


@pytest.mark.parametrize("erro", [Recusado("Portal recusou (413): arquivo acima do limite"), PermissionError("em uso")])
def test_recusa_ou_arquivo_ilegivel_nao_trava_a_fila(tmp_path: Path, erro: Exception) -> None:
    log, transporte = io.StringIO(), _Recusa(erro)
    a = Automacao(transporte, FilaLocal(tmp_path / "f.db"), log_local=log)
    a.arquivo(_arquivo(tmp_path, "a.txt"))
    a.arquivo(_arquivo(tmp_path, "b.txt"))
    assert transporte.tentativas == 2 and a.arquivos_pendentes == 0  # tentou os dois, uma vez cada
    assert f"arquivo 'a.txt' não enviado: {erro}" in log.getvalue()
    a.fechar()


# -- arquivos no modo agente: ficam na pasta de artefatos da tentativa -----------------------------
def test_modo_agente_copia_para_os_artefatos_sem_sobrescrever(tmp_path: Path) -> None:
    artefatos = tmp_path / "artefatos"
    transporte = TransporteAgente("pipe-x", "token-x", artefatos / "passos")
    origem = _arquivo(tmp_path, "Resumo.xlsx")
    transporte.enviar_arquivo(origem, "Resumo.xlsx", "5081", "application/octet-stream")
    transporte.enviar_arquivo(origem, "Resumo.xlsx", "5082", "application/octet-stream")
    assert sorted(p.name for p in artefatos.iterdir()) == ["Resumo (2).xlsx", "Resumo.xlsx"]
    assert (artefatos / "Resumo (2).xlsx").read_bytes() == CONTEUDO and origem.exists()
    assert not list(artefatos.glob("*.tmp"))


# -- declaração ao conectar --------------------------------------------------------------------
class _Instancia:
    id = "dri_teste"

    def __init__(self, recebe: list[bool], falhas: int = 0, erro: Exception | None = None) -> None:
        self.recebe, self.falhas, self.erro = list(recebe), falhas, erro
        self.declaracoes: list[dict] = []
        self.voltas = 0

    def status(self):
        recebe = self.recebe.pop(0) if len(self.recebe) > 1 else self.recebe[0]
        return {"status": "aprovada" if recebe else "pendente", "recebe_jobs": recebe}

    def declarar(self, dados):
        if self.falhas:
            self.falhas -= 1
            raise FalhaDeTransporte("Portal indisponível")
        if self.erro:
            raise self.erro
        self.declaracoes.append(dados)
        return {"entrada": {"novos": ["competencia"], "fora_de_uso": ["modo"], "voltaram": []},
                "tabela": {"novos": 3, "alterados": 1, "iguais": 0, "erros": 0}}

    def proximo_job(self, espera=30):
        self.voltas += 1
        return None


@pytest.fixture(autouse=True)
def sem_espera(monkeypatch):
    monkeypatch.setattr(modulo_instancia.time, "sleep", lambda s: None)


DECLARACAO = {"parametros": [{"chave": "competencia", "rotulo": "Competência", "tipo": "mes_ano"}]}


def test_declara_uma_vez_ao_receber_jobs_e_de_novo_se_voltar_a_ser_aprovada() -> None:
    inst, avisos = _Instancia([False, True, True, False, True, True]), []
    trabalhar(inst, lambda j, a: None, parar=lambda: inst.voltas >= 4, avisar=avisos.append, declaracao=DECLARACAO)
    assert inst.declaracoes == [DECLARACAO, DECLARACAO]
    assert "declaração enviada: 1 campo(s) novo(s); 1 fora de uso; tabela: 3 novo(s), 1 alterado(s) para aprovar" in avisos


def test_declaracao_montada_na_hora_e_rede_fora_tenta_de_novo() -> None:
    inst, chamadas = _Instancia([True], falhas=2), []

    def montar():
        chamadas.append(1)
        return DECLARACAO

    trabalhar(inst, lambda j, a: None, parar=lambda: inst.voltas >= 2, avisar=lambda m: None, declaracao=montar)
    assert inst.declaracoes == [DECLARACAO] and len(chamadas) == 3  # duas falhas de rede, depois foi


@pytest.mark.parametrize("erro,trecho", [
    (Recusado("Portal recusou (422): declaração inválida"), "declaração recusada: Portal recusou (422)"),
    (ValueError("JSON quebrado"), "declaração não montada: ValueError: JSON quebrado"),
])
def test_declaracao_com_problema_avisa_e_o_trabalho_segue(erro, trecho) -> None:
    inst, avisos = _Instancia([True], erro=erro), []
    trabalhar(inst, lambda j, a: None, parar=lambda: inst.voltas >= 3, avisar=avisos.append, declaracao=DECLARACAO)
    assert inst.voltas == 3 and sum(trecho in m for m in avisos) == 1  # avisou uma vez e seguiu pedindo jobs


def test_sem_declaracao_nada_e_enviado() -> None:
    inst = _Instancia([True])
    trabalhar(inst, lambda j, a: None, parar=lambda: inst.voltas >= 2, avisar=lambda m: None)
    assert inst.declaracoes == []
