"""Notificações (Fase 6): o que vira aviso, quem recebe e quando não repetir.

Cinco tipos: erro, item aguardando uma pessoa (atenção), máquina offline, fila parada há
mais de um tempo que cada pessoa escolhe, e término de execução. Cada pessoa liga só o que
quer receber (nada vem ligado).

Uma **ocorrência** é o evento agregado: a mesma execução que termina com erro é uma
ocorrência só (tipos ``erro`` e ``termino``), e cada endereço recebe no máximo um aviso
por ocorrência. A chave da ocorrência é estável: detectar de novo não cria outra.

Regras de quem recebe:
- erro, atenção e término: só quem pode ver a automação;
- máquina offline e fila parada: só administradores e gestores (decisão de 10/11/2026);
- fila parada: só quem escolheu exatamente aquele tempo.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

ERRO, ATENCAO, MAQUINA_OFFLINE, FILA_PARADA, TERMINO = "erro", "atencao", "maquina_offline", "fila_parada", "termino"
TIPOS = (ERRO, ATENCAO, MAQUINA_OFFLINE, FILA_PARADA, TERMINO)
SO_GESTORES = frozenset({MAQUINA_OFFLINE, FILA_PARADA})

FILA_MINUTOS_PADRAO = 30
FILA_MINUTOS_LIMITES = (5, 24 * 60)
# Ocorrência mais velha que isto não vira aviso: ligar o recurso (ou voltar de uma parada)
# não pode despejar avisos antigos.
JANELA_DE_DETECCAO = timedelta(hours=24)

SITUACOES_DE_ERRO = frozenset({"failed", "timed_out", "partially_succeeded"})


@dataclass(frozen=True)
class Ocorrencia:
    chave: str
    tipos: frozenset[str]
    titulo: str
    texto: str
    quando: datetime
    automation_id: int | None = None
    execution_id: str | None = None
    link: str | None = None
    fila_minutos: int | None = None


@dataclass(frozen=True)
class Pessoa:
    user_id: int
    email: str | None
    gestor: bool
    tipos: frozenset[str] = field(default_factory=frozenset)
    fila_minutos: int = FILA_MINUTOS_PADRAO


class PreferenciaInvalida(ValueError):
    pass


def validar_preferencia(tipos: Iterable[str], fila_minutos: int, gestor: bool) -> tuple[frozenset[str], int]:
    escolhidos = frozenset(tipos)
    desconhecidos = escolhidos - frozenset(TIPOS)
    if desconhecidos:
        raise PreferenciaInvalida(f"tipo desconhecido: {', '.join(sorted(desconhecidos))}")
    if not gestor and escolhidos & SO_GESTORES:
        raise PreferenciaInvalida("máquina offline e fila parada são só para administradores e gestores")
    minimo, maximo = FILA_MINUTOS_LIMITES
    if not minimo <= fila_minutos <= maximo:
        raise PreferenciaInvalida(f"o tempo da fila parada vai de {minimo} a {maximo} minutos")
    return escolhidos, fila_minutos


def _endereco(email: str | None) -> str | None:
    limpo = (email or "").strip().lower()
    return limpo if "@" in limpo else None


def destinatarios(ocorrencia: Ocorrencia, pessoas: Iterable[Pessoa],
                  pode_ver: Callable[[Pessoa, int], bool]) -> list[tuple[int, str]]:
    """``(user_id, endereço)`` de quem recebe; um por endereço, na ordem das pessoas."""
    saida: list[tuple[int, str]] = []
    vistos: set[str] = set()
    for pessoa in pessoas:
        tipos = ocorrencia.tipos & pessoa.tipos
        if not pessoa.gestor:
            tipos = tipos - SO_GESTORES
        if FILA_PARADA in tipos and pessoa.fila_minutos != ocorrencia.fila_minutos:
            tipos = tipos - {FILA_PARADA}
        if not tipos:
            continue
        if ocorrencia.automation_id is not None and not pode_ver(pessoa, ocorrencia.automation_id):
            continue
        endereco = _endereco(pessoa.email)
        if endereco is None or endereco in vistos:
            continue
        vistos.add(endereco)
        saida.append((pessoa.user_id, endereco))
    return saida


def recente(quando: datetime | None, agora: datetime) -> bool:
    return quando is not None and agora - quando <= JANELA_DE_DETECCAO


def fim_de_execucao(execution_id: str, situacao: str, automation_id: int | None, automacao: str | None,
                    quando: datetime, falha: str | None = None) -> Ocorrencia:
    """Execução que terminou: é ``termino`` sempre e também ``erro`` quando falhou."""
    nome = automacao or "Automação"
    erro = situacao in SITUACOES_DE_ERRO
    tipos = frozenset({TERMINO, ERRO}) if erro else frozenset({TERMINO})
    if situacao == "partially_succeeded":
        titulo = f"{nome}: terminou com erro em parte dos itens"
        texto = f"A execução {execution_id} terminou, mas parte dos itens falhou." + (f" Motivo: {falha}" if falha else "")
    elif erro:
        titulo = f"{nome}: terminou com erro"
        texto = f"A execução {execution_id} terminou com erro." + (f" Motivo: {falha}" if falha else "")
    elif situacao == "cancelled":
        titulo = f"{nome}: cancelada"
        texto = f"A execução {execution_id} foi cancelada." + (f" Motivo: {falha}" if falha else "")
    else:
        titulo, texto = f"{nome}: concluída", f"A execução {execution_id} terminou."
    return Ocorrencia(f"fim:{execution_id}", tipos, titulo, texto, quando, automation_id, execution_id,
                      f"/execucoes/{execution_id}")


def atencao(execution_id: str, item: str | None, motivo: str | None, automation_id: int | None,
            automacao: str | None, quando: datetime) -> Ocorrencia:
    """Item aguardando uma pessoa: um aviso por execução e item."""
    nome = automacao or "Automação"
    alvo = f"O item {item}" if item else "A execução"
    texto = f"{alvo} precisa de uma pessoa" + (f": {motivo}" if motivo else ".")
    return Ocorrencia(f"atencao:{execution_id}:{item or '-'}", frozenset({ATENCAO}), f"{nome}: precisa de uma pessoa",
                      texto, quando, automation_id, execution_id, f"/execucoes/{execution_id}")


def sem_comunicacao(execution_id: str, attempt_id: str, automation_id: int | None, automacao: str | None,
                    desde: datetime) -> Ocorrencia:
    """A automação parou de falar com o Portal (modo direto). Um aviso por tentativa; o Portal
    espera até 2 min e então cancela a execução (aí vem o aviso de término)."""
    nome = automacao or "Automação"
    return Ocorrencia(f"sem_comunicacao:{attempt_id}", frozenset({ERRO}), f"{nome}: comunicação não está ativa",
                      "A automação parou de responder ao Portal. O Portal espera até 2 min; sem retorno, a execução "
                      "é cancelada.", desde, automation_id, execution_id, f"/execucoes/{execution_id}")


def cancelamento_sem_resposta(execution_id: str, attempt_id: str, automation_id: int | None, automacao: str | None,
                              recebido: bool, desde: datetime) -> Ocorrencia:
    """Cancelamento pedido e não atendido em 2 min. Um aviso por tentativa."""
    nome = automacao or "Automação"
    texto = ("A automação recebeu o cancelamento e não parou em 2 min." if recebido
             else "A automação não recebeu o cancelamento em 2 min.")
    return Ocorrencia(f"cancelamento_sem_resposta:{attempt_id}", frozenset({ERRO}),
                      f"{nome}: o cancelamento não foi atendido", texto + " Confira a máquina ou use Encerrar no Portal.",
                      desde, automation_id, execution_id, f"/execucoes/{execution_id}")


def maquina_offline(maquina_id: str, nome: str, ultimo_sinal: datetime | None, online: bool,
                    agora: datetime) -> Ocorrencia | None:
    """Uma ocorrência por queda (o último sinal identifica a queda). Máquina que nunca deu
    sinal, ou que caiu há mais de um dia, não vira aviso. O horário vai em ``quando`` (a
    tela mostra no fuso de quem lê), nunca no texto."""
    if online or not recente(ultimo_sinal, agora):
        return None
    assert ultimo_sinal is not None
    return Ocorrencia(f"offline:{maquina_id}:{ultimo_sinal.isoformat()}", frozenset({MAQUINA_OFFLINE}),
                      f"Máquina {nome} offline", f"A máquina {nome} parou de dar sinal.", ultimo_sinal, link="/maquinas")


def fila_parada(esperando_desde: list[datetime], ultimo_inicio: datetime | None, agora: datetime,
                minutos: int) -> Ocorrencia | None:
    """Fila parada: há job esperando e nenhum começou há ``minutos``.

    A parada conta a partir do mais recente entre o job mais antigo na fila e o último
    início; essa marca identifica a parada, então cada parada avisa uma vez por tempo."""
    if not esperando_desde:
        return None
    desde = min(esperando_desde)
    if ultimo_inicio is not None and ultimo_inicio > desde:
        desde = ultimo_inicio
    if agora - desde < timedelta(minutes=minutos) or not recente(desde, agora):
        return None
    return Ocorrencia(f"fila_parada:{desde.isoformat()}:{minutos}", frozenset({FILA_PARADA}),
                      "Fila parada",
                      f"{len(esperando_desde)} job(s) esperando e nenhum começou há mais de {minutos} min.",
                      agora, link="/fila", fila_minutos=minutos)
