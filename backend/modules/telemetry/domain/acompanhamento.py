"""O que está acontecendo agora numa execução, a partir dos eventos da automação.

Função pura (sem banco): recebe os eventos do contrato ``automation-events/v1`` e
devolve etapa e item em andamento, progresso, a tela atual com "N s nesta tela"
(decisão 11), os passos com imagem, as atenções, a pausa em curso, a espera declarada e
o último sinal. ``situacao_do_agora`` resume tudo isso numa linha para o Painel.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

# Sem nenhum evento da automação por mais que isso, o Painel avisa "sem sinal" (decisão de 12/11/2026).
SEM_SINAL = timedelta(minutes=10)


@dataclass(frozen=True)
class EventoDaAutomacao:
    id: str
    tipo: str
    payload: dict[str, Any]
    quando: datetime
    tentativa: str
    sequencia: int = 0


def _abertos(eventos: list[EventoDaAutomacao], inicio: str, fim: str, chave: tuple[str, ...]) -> list[EventoDaAutomacao]:
    """Inícios sem o fim correspondente (mesma chave), na ordem em que começaram."""
    abertos: dict[tuple, EventoDaAutomacao] = {}
    for e in eventos:
        k = (e.tentativa, *(e.payload.get(c) for c in chave))
        if e.tipo == inicio:
            abertos[k] = e
        elif e.tipo == fim:
            abertos.pop(k, None)
    return sorted(abertos.values(), key=lambda e: (e.quando, e.sequencia, e.id))


def _iso(valor: datetime | None) -> str | None:
    return valor.isoformat() if valor else None


def _e_espera(e: EventoDaAutomacao) -> bool:
    return e.tipo == "espera.atualizada" or (e.tipo == "log" and bool(e.payload.get("espera")))


def _espera(atuais: list[EventoDaAutomacao]) -> dict[str, Any] | None:
    """A automação está esperando quando os últimos eventos são só de espera (``espera.atualizada``
    ou log marcado ``espera``). Qualquer outro evento depois disso encerra a espera."""
    seguidos: list[EventoDaAutomacao] = []
    for e in reversed(atuais):
        if not _e_espera(e):
            break
        seguidos.append(e)
    if not seguidos:
        return None
    ultimo, primeiro = seguidos[0], seguidos[-1]
    declarados = [d for d in (_data(e.payload.get("desde")) for e in seguidos if e.tipo == "espera.atualizada") if d]
    desde = min([primeiro.quando, *declarados])
    rotulo = ultimo.payload.get("rotulo") if ultimo.tipo == "espera.atualizada" else ultimo.payload.get("texto")
    return {"rotulo": (str(rotulo)[:160] if rotulo else None), "desde": _iso(desde), "item": ultimo.payload.get("item")}


def situacao_do_agora(*, job_status: str, parada: dict[str, Any] | None, pausa: dict[str, Any] | None,
                      espera: dict[str, Any] | None, ultimo_sinal: datetime | None, desde: datetime | None,
                      agora: datetime, sinal_da_instancia: datetime | None = None,
                      aviso_sem_comunicacao: timedelta | None = None, sem_comunicacao: timedelta | None = None,
                      prazo_do_cancelamento: timedelta | None = None) -> dict[str, Any] | None:
    """Uma linha só para o cartão do Painel, da mais importante para a menos: cancelamento sem
    resposta (erro), comunicação não ativa, cancelando, parada pedida, pausa declarada, espera
    declarada, sem sinal da automação. ``None``: rodando normal.

    ``sinal_da_instancia`` (modo direto): o último pedido da instância ao Portal. Os prazos vêm de
    ``modules.dispatch.domain.comunicacao``."""
    pedido_em = parada.get("pedido_em") if parada else None
    if (parada and parada.get("tipo") == "cancelar" and prazo_do_cancelamento is not None and pedido_em is not None
            and agora - pedido_em >= prazo_do_cancelamento):
        return {"tipo": "cancelamento_sem_resposta", "desde": _iso(pedido_em), "recebido": bool(parada.get("recebido_em"))}
    if (sinal_da_instancia is not None and aviso_sem_comunicacao is not None
            and agora - sinal_da_instancia >= aviso_sem_comunicacao):
        return {"tipo": "sem_comunicacao", "desde": _iso(sinal_da_instancia),
                "cancela_em": _iso(sinal_da_instancia + sem_comunicacao) if sem_comunicacao else None}
    if job_status == "cancelling" or (parada and parada.get("tipo") == "cancelar"):
        return {"tipo": "cancelando", "desde": _iso(parada.get("pedido_em")) if parada else None,
                "recebido": bool(parada and parada.get("recebido_em"))}
    if parada and parada.get("tipo") == "parar_apos_item":
        return {"tipo": "parando", "desde": _iso(parada.get("pedido_em")), "recebido": bool(parada.get("recebido_em"))}
    if pausa:
        return {"tipo": "pausa", "motivo": pausa.get("motivo"), "detalhe": pausa.get("detalhe"), "desde": pausa.get("desde")}
    if espera:
        return {"tipo": "espera", "rotulo": espera.get("rotulo"), "desde": espera.get("desde")}
    referencia = ultimo_sinal or desde
    if referencia is not None and agora - referencia > SEM_SINAL:
        return {"tipo": "sem_sinal", "desde": _iso(referencia)}
    return None


def _data(texto: Any) -> datetime | None:
    if not isinstance(texto, str):
        return None
    try:
        return datetime.fromisoformat(texto.replace("Z", "+00:00"))
    except ValueError:
        return None


def estado(eventos: list[EventoDaAutomacao], agora: datetime, *, rodando: bool, limite_passos: int = 60) -> dict[str, Any]:
    ordenados = sorted(eventos, key=lambda e: (e.quando, e.sequencia, e.id))
    # Só a tentativa mais recente descreve o "agora"; as anteriores ficam no histórico de passos.
    ultima = ordenados[-1].tentativa if ordenados else None
    atuais = [e for e in ordenados if e.tentativa == ultima]

    etapas = _abertos(atuais, "etapa.iniciada", "etapa.concluida", ("etapa", "item"))
    itens = _abertos(atuais, "item.iniciado", "item.concluido", ("item",))
    pausas = _abertos(atuais, "pausa.iniciada", "pausa.concluida", ("motivo", "item"))
    progresso = next((e for e in reversed(atuais) if e.tipo == "progresso"), None)
    conclusao = next((e for e in reversed(atuais) if e.tipo == "execucao.concluida"), None)

    passos = [e for e in ordenados if e.tipo == "passo"]
    com_imagem = [e for e in passos if e.payload.get("imagem_id")]
    tela = None
    if com_imagem:
        ultimo = com_imagem[-1]
        espera = next((e for e in reversed(atuais) if e.tipo == "espera.atualizada" and e.quando >= ultimo.quando), None)
        desde = (_data(espera.payload.get("desde")) if espera else None) or ultimo.quando
        tela = {
            "imagem_id": ultimo.payload["imagem_id"],
            "rotulo": ultimo.payload.get("rotulo"),
            "tipo": ultimo.payload.get("tipo"),
            "item": ultimo.payload.get("item"),
            "quando": _iso(ultimo.quando),
            "desde": _iso(desde),
            # Só conta enquanto roda: depois do fim, "há N s nesta tela" não faz sentido.
            "segundos_nesta_tela": max(int((agora - desde).total_seconds()), 0) if rodando and desde else None,
            "espera_rotulo": espera.payload.get("rotulo") if espera else None,
        }

    return {
        "etapa_atual": None if not etapas else {
            "etapa": etapas[-1].payload.get("etapa"), "item": etapas[-1].payload.get("item"),
            "desde": _iso(etapas[-1].quando), "tarefas_previstas": etapas[-1].payload.get("tarefas_previstas")},
        "item_atual": None if not itens else {
            "item": itens[-1].payload.get("item"), "rotulo": itens[-1].payload.get("rotulo"), "desde": _iso(itens[-1].quando)},
        "progresso": None if progresso is None else {
            "atual": progresso.payload.get("atual"), "total": progresso.payload.get("total"),
            "rotulo": progresso.payload.get("rotulo"), "item": progresso.payload.get("item")},
        "pausa": None if not pausas else {
            "motivo": pausas[-1].payload.get("motivo"), "detalhe": pausas[-1].payload.get("detalhe"),
            "desde": _iso(pausas[-1].quando)},
        "conclusao": None if conclusao is None else {
            "situacao": conclusao.payload.get("situacao"), "resumo": conclusao.payload.get("resumo"),
            "quando": _iso(conclusao.quando)},
        "tela": tela,
        "passos": [{"id": e.id, "rotulo": e.payload.get("rotulo"), "tipo": e.payload.get("tipo"),
                    "imagem_id": e.payload.get("imagem_id"), "item": e.payload.get("item"), "quando": _iso(e.quando)}
                   for e in passos[-limite_passos:]],
        "atencoes": [{"id": e.id, "item": e.payload.get("item"), "motivo": e.payload.get("motivo"), "quando": _iso(e.quando)}
                     for e in ordenados if e.tipo == "atencao"],
        "espera": _espera(atuais) if rodando and not pausas else None,
        "ultimo_sinal": atuais[-1].quando if atuais else None,
    }
