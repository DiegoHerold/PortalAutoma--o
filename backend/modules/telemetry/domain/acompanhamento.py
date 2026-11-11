"""O que está acontecendo agora numa execução, a partir dos eventos da automação.

Função pura (sem banco): recebe os eventos do contrato ``automation-events/v1`` e
devolve etapa e item em andamento, progresso, a tela atual com "N s nesta tela"
(decisão 11), os passos com imagem, as atenções e a pausa em curso.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


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
    }
