"""Painel (Fase 5): o que está rodando agora, as máquinas, a linha do tempo e o Histórico.

- ``GET /painel``: cada execução rodando com etapa, item, progresso, decorrido, falta,
  término previsto e, com permissão de telas e logs, a tela atual e as últimas linhas do
  log. Quem tem ``central_de_telas`` (admin) vê todas: é a Central de telas.
- ``GET /painel/linha-do-tempo``: por máquina, o que rodou, o que roda e o que a fila prevê.
- ``GET /historico``: execuções terminadas, com o tempo real ao lado do previsto.
- ``GET /painel/avisos``: SSE que avisa quando qualquer execução ou a fila muda.
- ``GET /painel/recentes``: as últimas automações que a pessoa pode ver, com a última execução
  de cada (para executar de novo dali), e o filtro por máquina.
- ``GET /painel/executaveis``: as automações que a pessoa pode executar (busca rápida).
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
from modules.access.domain.concessao import CENTRAL_DE_TELAS, CONTROLAR, EXECUTAR, VER_EXECUCOES, VER_TELAS_E_LOGS
from modules.access.infrastructure.adapters import build_access_adapters
from modules.dispatch.domain.linha_do_tempo import FEITO, PREVISTO, RODANDO, Bloco, marcas, montar
from modules.telemetry.api.acompanhar import fluxo_de_avisos, usuario_do_cabecalho
from modules.telemetry.application.use_cases.estimates import QueueEstimates
from modules.telemetry.domain.acompanhamento import estado, situacao_do_agora
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


from modules.dispatch.domain.comunicacao import AVISO_SEM_COMUNICACAO, PRAZO_DO_CANCELAMENTO, SEM_COMUNICACAO  # noqa: E402

PRAZOS = {"aviso_sem_comunicacao": AVISO_SEM_COMUNICACAO, "sem_comunicacao": SEM_COMUNICACAO,
          "prazo_do_cancelamento": PRAZO_DO_CANCELAMENTO}


def _paradas_pedidas(db: Session, tentativas: list[str]) -> dict[str, dict[str, Any]]:
    from modules.dispatch.infrastructure.repositories.sqlalchemy_job_tokens import SqlAlchemyDirectCommandStore

    return SqlAlchemyDirectCommandStore(db).paradas_pedidas(tentativas)


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
    rodando = leitor.rodando()
    paradas = _paradas_pedidas(db, [r["tentativa_id"] for r in rodando])
    for r in rodando:
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
            "situacao": situacao_do_agora(job_status=r["job_status"], parada=paradas.get(r["tentativa_id"]),
                                          pausa=agora_da_tela["pausa"], espera=agora_da_tela["espera"],
                                          ultimo_sinal=agora_da_tela["ultimo_sinal"], desde=r["desde"], agora=agora,
                                          sinal_da_instancia=r["sinal_da_instancia"], **PRAZOS),
            "pode_controlar": permissoes.pode(r["automation_id"], CONTROLAR),
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
              dias: int | None = Query(default=None, ge=1, le=3650), limite: int = Query(default=30, ge=1, le=100),
              db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    try:
        antes_de = datetime.fromisoformat(antes) if antes else None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="antes: data inválida.") from exc
    permissoes = _Permissoes(db, user)
    linhas, cursor = SqlAlchemyPainelReader(db).historico(busca=busca, automation_id=automacao, situacao=situacao,
                                                          antes_de=antes_de, limite=limite, desde=_desde(dias))
    return {"execucoes": [l for l in linhas if permissoes.pode(l["automation_id"], VER_EXECUCOES)], "cursor": cursor}


@router.get("/painel/recentes")
def recentes(maquina: str | None = Query(default=None, max_length=80), limite: int = Query(default=3, ge=1, le=12),
             db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    """Uma linha por automação (a execução mais recente dela), só das que a pessoa vê."""
    permissoes = _Permissoes(db, user)
    leitor = SqlAlchemyPainelReader(db)
    automacoes: list[dict[str, Any]] = []
    vistas: set[int] = set()
    for e in leitor.ultimas_execucoes(machine_id=maquina):
        if e["automation_id"] in vistas or not permissoes.pode(e["automation_id"], VER_EXECUCOES):
            continue
        vistas.add(e["automation_id"])
        automacoes.append({"automation_id": e["automation_id"], "automacao": e["automacao"],
                           "pode_executar": permissoes.acesso.pode(user, e["automation_id"], EXECUTAR),
                           "pode_controlar": permissoes.acesso.pode(user, e["automation_id"], CONTROLAR),
                           "ultima": {k: e[k] for k in ("execucao_id", "status", "quando", "maquinas", "itens",
                                                        "continuada_em")}})
        if len(automacoes) >= limite:
            break
    return {"automacoes": automacoes, "maquinas": [{"id": i, "nome": n} for i, n in leitor.maquinas()]}


@router.get("/painel/executaveis")
def executaveis(db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    """Para o botão "Executar automação" do Painel: só o que a pessoa pode executar."""
    acesso = acesso_por_automacao(db)
    return {"automacoes": [a for a in SqlAlchemyPainelReader(db).automacoes_ativas() if acesso.pode(user, a["id"], EXECUTAR)]}


def _desde(dias: int | None) -> datetime | None:
    """Os últimos ``dias`` dias contando o de hoje (1 = só hoje), no fuso de São Paulo."""
    if not dias:
        return None
    from zoneinfo import ZoneInfo

    hoje = datetime.now(ZoneInfo("America/Sao_Paulo")).replace(hour=0, minute=0, second=0, microsecond=0)
    return hoje - timedelta(days=dias - 1)


@router.get("/historico/resumo")
def resumo_do_historico(dias: int | None = Query(default=7, ge=1, le=3650), automacao: int | None = None,
                        db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    """Quantas execuções terminaram no período, quantas deram certo, falharam ou pararam, e o tempo médio."""
    permissoes = _Permissoes(db, user)
    linhas = [l for l in SqlAlchemyPainelReader(db).resumo(desde=_desde(dias), automation_id=automacao)
              if permissoes.pode(l["automation_id"], VER_EXECUCOES)]
    duracoes = [l["duracao_s"] for l in linhas if l["duracao_s"] is not None and l["status"] in ("succeeded", "partially_succeeded")]
    conta = lambda *s: sum(1 for l in linhas if l["status"] in s)  # noqa: E731
    return {"dias": dias, "total": len(linhas), "concluidas": conta("succeeded", "partially_succeeded"),
            "com_falha": conta("failed", "timed_out", "lost"), "canceladas": conta("cancelled"),
            "duracao_media_s": round(sum(duracoes) / len(duracoes)) if duracoes else None}


@router.get("/painel/avisos")
def avisos(request: Request, fabrica: Any = Depends(get_session_factory)) -> StreamingResponse:
    with fabrica() as db:
        usuario_do_cabecalho(db, request)
    return fluxo_de_avisos(request, "*", "*")
