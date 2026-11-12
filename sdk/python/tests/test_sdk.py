"""SDK: contrato, fila local, API da automação e imagens, com um transporte em memória."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest
from PIL import Image, ImageDraw

from portal_automacoes import Automacao, EventoInvalido, ParadaSolicitada
from portal_automacoes import eventos as ev
from portal_automacoes.fila import FilaLocal
from portal_automacoes.transporte import FalhaDeTransporte

RAIZ_REPO = Path(__file__).resolve().parents[3]


class TransporteMemoria:
    """Receptor em memória: idempotente por sequência, pode cair e voltar."""

    nome = "memoria"

    def __init__(self) -> None:
        self.recebidos: list[dict[str, Any]] = []
        self.imagens: dict[str, bytes] = {}
        self.fora_do_ar = False
        self.comandos_pendentes: list[dict[str, Any]] = []
        self.conexoes = 0

    def conectar(self) -> int:
        if self.fora_do_ar:
            raise FalhaDeTransporte("fora do ar")
        self.conexoes += 1
        return max((e["sequence"] for e in self.recebidos), default=0)

    def enviar(self, eventos: list[dict[str, Any]]) -> int:
        if self.fora_do_ar:
            raise FalhaDeTransporte("fora do ar")
        ultima = max((e["sequence"] for e in self.recebidos), default=0)
        for evento in eventos:
            if evento["sequence"] > ultima:
                self.recebidos.append(evento)
                ultima = evento["sequence"]
        return ultima

    def comandos(self) -> list[dict[str, Any]]:
        pendentes, self.comandos_pendentes = self.comandos_pendentes, []
        return pendentes

    def enviar_imagem(self, imagem_id: str, jpeg: bytes) -> None:
        self.imagens[imagem_id] = jpeg

    def fechar(self) -> None:
        return None

    def tipos(self) -> list[str]:
        return [e["type"] for e in self.recebidos]


@pytest.fixture
def transporte() -> TransporteMemoria:
    return TransporteMemoria()


@pytest.fixture
def automacao(transporte: TransporteMemoria, tmp_path: Path) -> Automacao:
    return Automacao(transporte, FilaLocal(tmp_path / "fila.db"), "teste-1.0", log_local=io.StringIO())


def _tela() -> Image.Image:
    imagem = Image.new("RGB", (200, 120), (240, 240, 240))
    ImageDraw.Draw(imagem).rectangle((20, 20, 180, 100), outline=(20, 40, 69), width=4)
    return imagem


# -- contrato ---------------------------------------------------------------------

@pytest.mark.parametrize("nome", ["automation-event.schema.json", "automation-command.schema.json"])
def test_copia_do_contrato_no_sdk_e_identica_a_de_contracts(nome: str) -> None:
    oficial = RAIZ_REPO / "contracts" / "automation-events" / "v1" / nome
    copia = RAIZ_REPO / "sdk" / "python" / "portal_automacoes" / "contrato" / nome
    if not oficial.is_file():
        pytest.skip("contracts/ não está ao lado (branch sdk-python, só com o SDK)")
    assert copia.read_bytes() == oficial.read_bytes(), "rode: copie contracts/automation-events/v1/*.schema.json para o SDK"


def test_evento_montado_cumpre_o_contrato_e_omite_campos_vazios() -> None:
    evento = ev.montar(3, "passo", {"rotulo": "Gerar acionado", "tipo": "acao", "imagem_id": None})
    assert evento["protocol_version"] == "automation-events/1"
    assert evento["sequence"] == 3
    assert "imagem_id" not in evento["payload"]
    assert evento["occurred_at"].endswith("Z")


@pytest.mark.parametrize("tipo,payload", [
    ("log", {"nivel": "verbose", "texto": "x"}),
    ("etapa.concluida", {"etapa": "rubricas", "situacao": "parcial"}),
    ("progresso", {"atual": 5, "total": 4}),
    ("atencao", {"motivo": "sem item"}),
])
def test_evento_fora_do_contrato_e_erro_de_programacao(tipo: str, payload: dict) -> None:
    with pytest.raises(EventoInvalido):
        ev.montar(1, tipo, payload)


# -- fluxo da automação ---------------------------------------------------------------

def test_fluxo_completo_emite_os_eventos_na_ordem(automacao: Automacao, transporte: TransporteMemoria) -> None:
    with automacao as a:
        with a.etapa("iniciar"):
            a.log("Abrindo")
        with a.item("5066", rotulo="Planet", grupo="5066", configuracao={"separar_por_custo": True}):
            with a.etapa("rubricas", tarefas_previstas=2) as etapa:
                a.progresso(1, 2, "centro 33")
                etapa.tarefa_concluida()
                a.progresso(2, 2, "centro 35")
                etapa.tarefa_concluida()
            a.resumo("2 relatórios")

    assert transporte.tipos() == [
        "execucao.iniciada", "etapa.iniciada", "log", "etapa.concluida", "item.iniciado", "etapa.iniciada",
        "progresso", "progresso", "etapa.concluida", "item.concluido", "execucao.concluida"]
    assert [e["sequence"] for e in transporte.recebidos] == list(range(1, 12))
    rubricas = transporte.recebidos[8]["payload"]
    assert rubricas == {"etapa": "rubricas", "item": "5066", "situacao": "ok", "tarefas": 2}
    assert transporte.recebidos[9]["payload"] == {"item": "5066", "situacao": "ok", "resumo": "2 relatórios"}
    assert transporte.recebidos[-1]["payload"]["situacao"] == "ok"


def test_excecao_na_etapa_marca_erro_no_item_e_na_execucao(automacao: Automacao, transporte: TransporteMemoria) -> None:
    with pytest.raises(RuntimeError):
        with automacao as a:
            with a.item("5081"):
                with a.etapa("txt"):
                    raise RuntimeError("a Domínio fechou durante o Gravar")

    por_tipo = {e["type"]: e["payload"] for e in transporte.recebidos}
    assert por_tipo["etapa.concluida"]["situacao"] == "erro"
    assert por_tipo["item.concluido"] == {"item": "5081", "situacao": "erro", "resumo": "a Domínio fechou durante o Gravar"}
    assert por_tipo["execucao.concluida"]["situacao"] == "erro"


def test_parada_solicitada_marca_interrompida(automacao: Automacao, transporte: TransporteMemoria) -> None:
    with pytest.raises(ParadaSolicitada):
        with automacao as a:
            with a.item("5066"):
                transporte.comandos_pendentes.append({"protocol_version": "automation-events/1", "command_id": "cmd_1",
                                                      "type": "parar_apos_item", "issued_at": "2026-11-09T14:00:00Z"})
                with a.etapa("rubricas"):
                    a.verificar_parada()

    por_tipo = {e["type"]: e["payload"] for e in transporte.recebidos}
    assert por_tipo["etapa.concluida"]["situacao"] == "interrompida"
    assert por_tipo["item.concluido"]["situacao"] == "cancelado"
    assert por_tipo["execucao.concluida"]["situacao"] == "interrompida"


def test_comando_fora_do_contrato_e_ignorado(automacao: Automacao, transporte: TransporteMemoria) -> None:
    transporte.comandos_pendentes.append({"type": "formatar_disco"})
    with automacao as a:
        assert a.deve_parar() is False


def test_atencao_marca_item_e_execucao(automacao: Automacao, transporte: TransporteMemoria) -> None:
    with automacao as a:
        with a.item("5066"):
            a.atencao("Rubricas a parametrizar", colunas=[("codigo", "Rubrica")], linhas=[{"codigo": 8781}])

    por_tipo = {e["type"]: e["payload"] for e in transporte.recebidos}
    assert por_tipo["atencao"]["tabela"]["linhas"] == [{"codigo": 8781}]
    assert por_tipo["item.concluido"]["situacao"] == "atencao"
    assert por_tipo["execucao.concluida"]["situacao"] == "atencao"


def test_atencao_fora_de_item_e_recusada(automacao: Automacao) -> None:
    with automacao as a, pytest.raises(EventoInvalido):
        a.atencao("sem item")


def test_pausa_emite_inicio_e_fim_mesmo_com_erro(automacao: Automacao, transporte: TransporteMemoria) -> None:
    with pytest.raises(OSError), automacao as a, a.pausa("reinicio", "Domínio travou"):
        raise OSError("travou")
    assert [t for t in transporte.tipos() if t.startswith("pausa")] == ["pausa.iniciada", "pausa.concluida"]


# -- fila local ----------------------------------------------------------------------

def test_transporte_fora_do_ar_nao_derruba_a_automacao_e_reenvia_em_ordem(
        automacao: Automacao, transporte: TransporteMemoria) -> None:
    transporte.fora_do_ar = True
    automacao.__enter__()
    automacao.log("primeiro")
    automacao.log("segundo")
    assert transporte.recebidos == []
    assert automacao.pendentes == 3

    transporte.fora_do_ar = False
    automacao.log("terceiro")

    assert [e["sequence"] for e in transporte.recebidos] == [1, 2, 3, 4]
    assert [e["payload"].get("texto") for e in transporte.recebidos[1:]] == ["primeiro", "segundo", "terceiro"]
    assert automacao.pendentes == 0
    automacao.__exit__(None, None, None)


def test_reconexao_nao_duplica_o_que_o_receptor_ja_tem(automacao: Automacao, transporte: TransporteMemoria) -> None:
    automacao.__enter__()
    automacao.log("um")
    automacao._conectado = False  # simula queda: a próxima emissão reconecta
    automacao.log("dois")
    assert [e["sequence"] for e in transporte.recebidos] == [1, 2, 3]
    assert transporte.conexoes == 2
    automacao.__exit__(None, None, None)


def test_fila_continua_a_sequencia_ao_reabrir(tmp_path: Path) -> None:
    arquivo = tmp_path / "fila.db"
    fila = FilaLocal(arquivo)
    for n in (1, 2, 3):
        fila.adicionar(ev.montar(n, "log", {"nivel": "info", "texto": str(n)}))
    fila.confirmar_ate(2)
    fila.fechar()

    reaberta = FilaLocal(arquivo)
    assert reaberta.ultima_sequencia() == 3
    assert [e["sequence"] for e in reaberta.pendentes()] == [3]
    reaberta.fechar()


# -- imagens -------------------------------------------------------------------------

def test_passo_com_imagem_envia_por_fora_e_referencia_o_id(automacao: Automacao, transporte: TransporteMemoria) -> None:
    with automacao as a:
        a.passo("Abriu: Rubricas", tipo="abriu", imagem=_tela())

    passo = next(e for e in transporte.recebidos if e["type"] == "passo")
    imagem_id = passo["payload"]["imagem_id"]
    assert imagem_id in transporte.imagens
    assert transporte.imagens[imagem_id][:2] == b"\xff\xd8"  # JPEG
    assert "imagem" not in passo["payload"]


@pytest.mark.parametrize("imagem", [
    Image.new("RGB", (200, 120), (128, 128, 128)),  # cinza
    Image.new("RGB", (200, 120), (0, 0, 0)),        # preta
    b"isto nao e uma imagem",                       # corrompida
])
def test_imagem_vazia_ou_corrompida_nunca_sai_da_maquina(
        automacao: Automacao, transporte: TransporteMemoria, imagem: Any) -> None:
    with automacao as a:
        a.passo("Gerar acionado", imagem=imagem)

    passo = next(e for e in transporte.recebidos if e["type"] == "passo")
    assert "imagem_id" not in passo["payload"]
    assert transporte.imagens == {}


# -- escolha do modo pela configuração --------------------------------------------------

def test_modo_vem_da_configuracao(tmp_path: Path) -> None:
    base = {"PORTAL_FILA_DIR": str(tmp_path)}
    assert Automacao.conectar(ambiente=base).modo == "desligado"
    assert Automacao.conectar(ambiente={**base, "AUTOMATION_EVENTS_PIPE": "p", "AUTOMATION_EVENTS_TOKEN": "t"}).modo == "agente"
    direto = {**base, "PORTAL_URL": "https://portal.intranet", "PORTAL_JOB_ID": "job_1", "PORTAL_JOB_TOKEN": "tok"}
    assert Automacao.conectar(ambiente=direto).modo == "direto"
    with pytest.raises(ValueError, match="PORTAL_MODO"):
        Automacao.conectar(ambiente={**base, "PORTAL_MODO": "magia"})


# -- automações que já existem (início e fim em pontos diferentes) ------------------------------

def test_item_e_etapa_sem_bloco_with(automacao: Automacao, transporte: TransporteMemoria) -> None:
    automacao.iniciar_etapa("iniciar", item=None)
    automacao.concluir_etapa("iniciar", item=None)
    automacao.iniciar_item(5081, rotulo="Matriz 5081", grupo=5081)
    automacao.iniciar_etapa("rubricas", tarefas_previstas=3)
    automacao.concluir_etapa("rubricas", situacao="erro", tarefas=2)
    automacao.concluir_item("erro", resumo="Rubricas: falhou no centro 3")
    automacao.concluir_item("ok")  # sem item aberto: nada
    automacao.fechar()
    pares = [(e["type"], e["payload"].get("item"), e["payload"].get("situacao")) for e in transporte.recebidos]
    assert pares == [("etapa.iniciada", None, None), ("etapa.concluida", None, "ok"), ("item.iniciado", "5081", None),
                     ("etapa.iniciada", "5081", None), ("etapa.concluida", "5081", "erro"),
                     ("item.concluido", "5081", "erro")]
    assert transporte.recebidos[4]["payload"]["tarefas"] == 2
    assert transporte.recebidos[5]["payload"]["resumo"] == "Rubricas: falhou no centro 3"


def test_emissao_de_varias_threads_nao_repete_nem_pula_sequencia(automacao: Automacao, transporte: TransporteMemoria) -> None:
    import threading

    def emitir(n: int) -> None:
        for i in range(50):
            automacao.log(f"thread {n} linha {i}")

    linhas = [threading.Thread(target=emitir, args=(n,)) for n in range(4)]
    for t in linhas:
        t.start()
    for t in linhas:
        t.join()
    automacao.fechar()
    assert [e["sequence"] for e in transporte.recebidos] == list(range(1, 201))
