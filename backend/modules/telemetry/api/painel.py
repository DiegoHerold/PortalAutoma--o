"""Painel (Fase 5): o que está rodando agora, as máquinas, a linha do tempo e o Histórico.

- ``GET /painel``: cada execução rodando com etapa, item, progresso, decorrido, falta,
  término previsto e, com permissão de telas e logs, a tela atual e as últimas linhas do
  log. Quem tem ``central_de_telas`` (admin) vê todas: é a Central de telas.
- ``GET /painel/linha-do-tempo``: por máquina, o que rodou, o que roda e o que a fila prevê.
- ``GET /historico``: execuções terminadas, com o tempo real ao lado do previsto.
- ``GET /painel/avisos``: SSE que avisa quando qualquer execução ou a fila muda.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from infrastructure.database import get_db, get_session_factory
from modules.access.api.authorization import acesso_por_automacao
from modules.access.api.dependencies import get_current_user
from modules.access.application.use_cases import PermissionChecker
from modules.access.domain.concessao import CENTRAL_DE_TELAS, VER_EXECUCOES, VER_TELAS_E_LOGS
from modules.access.infrastructure.adapters import build_access_adapters
from modules.dispatch.domain.linha_do_tempo import FEITO, PREVISTO, RODANDO, Bloco, marcas, montar
from modules.telemetry.api.acompanhar import fluxo_de_avisos, usuario_do_cabecalho
from modules.telemetry.application.use_cases.estimates import QueueEstimates
from modules.telemetry.domain.acompanhamento import estado
from modules.telemetry.infrastructure.adapters import build_telemetry_adapters
from modules.telemetry.infrastructure.repositories.sqlalchemy_images import SqlAlchemyStepImageRepository
from modules.telemetry.infrastructure.repositories.sqlalchemy_painel import SqlAlchemyPainelReader

router = APIRouter(tags=["painel"])

LINHAS_DE_LOG = 6
EVENTOS_DO_AGORA = 800


def _agora() -> datetime:
    return datetime.now(UTC)


class _Permissoes:
    """Consulta a permissão uma vez por automação no pedido."""

    def __init__(self, db: Session, user: Any) -> None:
        self.user = user
        self.acesso = acesso_por_automacao(db)
        self.central = PermissionChecker(build_access_adapters(db).access).has_permission(user, CENTRAL_DE_TELAS)
        self._cache: dict[tuple[int, str], bool] = {}

    def pode(self, automation_id: int | None, acao: str) -> bool:
        if automation_id is None:
            return False
        if self.central:
            return True
        chave = (automation_id, acao)
        if chave not in self._cache:
            self._cache[chave] = self.acesso.pode(self.user, automation_id, acao)
        return self._cache[chave]


def _fila(db: Session, agora: datetime) -> dict[str, Any]:
    from modules.dispatch.infrastructure.adapters.fila import build_fila

    return build_fila(db).ver.execute(agora)


@router.get("/painel")
def painel(db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    agora = _agora()
    permissoes = _Permissoes(db, user)
    leitor, imagens = SqlAlchemyPainelReader(db), SqlAlchemyStepImageRepository(db)
    t = build_telemetry_adapters(db)
    execucoes = []
    ocupadas: dict[str, str | None] = {}
    for r in leitor.rodando():
        visivel = permissoes.pode(r["automation_id"], VER_EXECUCOES)
        if r["maquina_id"]:
            ocupadas[r["maquina_id"]] = r["automacao"] if visivel else None
        if not visivel:
            continue
        telas = permissoes.pode(r["automation_id"], VER_TELAS_E_LOGS)
        agora_da_tela = estado(imagens.eventos_de_estado(r["execucao_id"], limite=EVENTOS_DO_AGORA), agora, rodando=True)
        estimativas = QueueEstimates(t.steps, t.manifests, t.items.plans, lambda _job, tid=r["tentativa_id"]: tid)
        falta, motivo = estimativas.restante(r["execucao_id"], r["job_id"], r["desde"], agora)
        tela = agora_da_tela["tela"] if telas else None
        if tela:
            tela["imagem"] = imagens.situacoes(r["execucao_id"]).get(tela["imagem_id"])
        execucoes.append({
            "execucao_id": r["execucao_id"], "job_id": r["job_id"], "automation_id": r["automation_id"],
            "automacao": r["automacao"], "maquina_id": r["maquina_id"], "maquina": r["maquina_nome"], "modo": r["modo"],
            "itens": r["itens"], "tentativa": r["tentativa"],
            "desde": r["desde"].isoformat() if r["desde"] else None,
            "decorrido_s": (agora - r["desde"]).total_seconds() if r["desde"] else None,
            "falta_s": falta, "motivo_sem_previsao": motivo,
            "termino_previsto": (agora + timedelta(seconds=falta)).isoformat() if falta is not None else None,
            "etapa": agora_da_tela["etapa_atual"], "item": agora_da_tela["item_atual"],
            "progresso": agora_da_tela["progresso"], "pausa": agora_da_tela["pausa"],
            "atencoes": len(agora_da_tela["atencoes"]),
            "pode_ver_tela": telas, "tela": tela,
            "log": imagens.logs(r["execucao_id"], depois_de=None, limite=LINHAS_DE_LOG, esconder_espera=True)[0] if telas else None,
        })

    visao = _fila(db, agora)
    proximos: dict[str, dict[str, Any]] = {}
    for job in visao["jobs"]:
        if job["maquina_prevista"] and job["maquina_prevista"] not in proximos:
            visivel = permissoes.pode(job["automation_id"], VER_EXECUCOES)
            proximos[job["maquina_prevista"]] = {"automacao": job["automacao"] if visivel else None,
                                                 "inicio_previsto": job["inicio_previsto"]}
    maquinas = [{
        "id": m["id"], "nome": m["nome"], "online": m["online"], "sessao_bloqueada": m["sessao_bloqueada"],
        "job_perdido": m["job_perdido"], "ocupada": bool(m["rodando"]) or m["id"] in ocupadas,
        "rodando": ocupadas.get(m["id"]), "proximo": proximos.get(m["id"]),
    } for m in visao["maquinas"]]
    visiveis = [j for j in visao["jobs"] if permissoes.pode(j["automation_id"], VER_EXECUCOES)]
    terminos = [j["termino_previsto"] for j in visiveis]
    return {
        "gerado_em": agora.isoformat(), "central": permissoes.central,
        "execucoes": execucoes, "maquinas": maquinas,
        "fila": {"esperando": len(visiveis), "perdidos": len(visao["perdidos"]),
                 "termina_em": max(terminos) if terminos and all(terminos) else None,
                 "sem_previsao": sum(1 for x in terminos if not x)},
    }


@router.get("/painel/linha-do-tempo")
def linha_do_tempo(horas_antes: int = Query(default=6, ge=1, le=48), horas_depois: int = Query(default=6, ge=1, le=48),
                   db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    agora = _agora()
    inicio, fim = agora - timedelta(hours=horas_antes), agora + timedelta(hours=horas_depois)
    permissoes = _Permissoes(db, user)
    leitor = SqlAlchemyPainelReader(db)
    rodando = {r["job_id"]: r for r in leitor.rodando()}
    blocos: list[Bloco] = []
    t = build_telemetry_adapters(db)
    for b in leitor.tentativas_desde(inicio):
        automacao = b["automacao"] if permissoes.pode(b["automation_id"], VER_EXECUCOES) else None
        if b["ativa"] and b["job_id"] in rodando:
            r = rodando[b["job_id"]]
            estimativas = QueueEstimates(t.steps, t.manifests, t.items.plans, lambda _job, tid=r["tentativa_id"]: tid)
            falta, _ = estimativas.restante(r["execucao_id"], r["job_id"], r["desde"], agora)
            fim_previsto = agora + timedelta(seconds=falta) if falta is not None else None
            blocos.append(Bloco(b["maquina_id"], RODANDO, b["inicio"], fim_previsto, b["execucao_id"] if automacao else None,
                                b["job_id"], automacao, tuple(b["itens"]) if automacao else (), "running"))
        elif not b["ativa"]:
            blocos.append(Bloco(b["maquina_id"], FEITO, b["inicio"], b["fim"], b["execucao_id"] if automacao else None,
                                b["job_id"], automacao, tuple(b["itens"]) if automacao else (), b["situacao"]))
    for job in _fila(db, agora)["jobs"]:
        if not job["maquina_prevista"] or not job["inicio_previsto"]:
            continue
        visivel = permissoes.pode(job["automation_id"], VER_EXECUCOES)
        blocos.append(Bloco(job["maquina_prevista"], PREVISTO, datetime.fromisoformat(job["inicio_previsto"]),
                            datetime.fromisoformat(job["termino_previsto"]) if job["termino_previsto"] else None,
                            None, job["job_id"], job["automacao"] if visivel else None,
                            tuple(job["itens"]) if visivel else (), "queued"))
    return {"inicio": inicio.isoformat(), "fim": fim.isoformat(), "agora": agora.isoformat(),
            "agora_posicao": round((agora - inicio).total_seconds() / (fim - inicio).total_seconds() * 100, 3),
            "marcas": marcas(inicio, fim), "maquinas": montar(leitor.maquinas(), blocos, inicio, fim, agora)}


@router.get("/historico")
def historico(busca: str | None = Query(default=None, max_length=120), automacao: int | None = None,
              situacao: str | None = Query(default=None, max_length=30), antes: str | None = None,
              limite: int = Query(default=30, ge=1, le=100),
              db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    try:
        antes_de = datetime.fromisoformat(antes) if antes else None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="antes: data inválida.") from exc
    permissoes = _Permissoes(db, user)
    linhas, cursor = SqlAlchemyPainelReader(db).historico(busca=busca, automation_id=automacao, situacao=situacao,
                                                          antes_de=antes_de, limite=limite)
    return {"execucoes": [l for l in linhas if permissoes.pode(l["automation_id"], VER_EXECUCOES)], "cursor": cursor}


@router.get("/painel/avisos")
def avisos(request: Request, fabrica: Any = Depends(get_session_factory)) -> StreamingResponse:
    with fabrica() as db:
        usuario_do_cabecalho(db, request)
    return fluxo_de_avisos(request, "*", "*")
