"""API das pendências (13/11/2026). Regras em ``aplicacao.py``.

- ``GET /pendencias``: as pendências aguardando, por execução, das automações que a pessoa vê.
- ``GET /pendencias/avisos/{id}``: o aviso do e-mail (o botão "Continuar processo" leva aqui).
- ``POST /pendencias/avisos/{id}/continuar``: continua os itens do aviso que ainda aguardam.
- ``GET /pendencias/execucoes/{id}``, ``POST /pendencias/execucoes/{id}/continuar`` (``{"itens": [...]}``
  opcional): o mesmo pela execução, no Portal.
Já continuado: ``409`` com ``resolucao`` (quando, quem, por onde e a execução nova).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from infrastructure.config import get_settings
from infrastructure.database import get_db
from modules.access.api.authorization import acesso_por_automacao
from modules.access.api.dependencies import get_current_user
from modules.orchestration.pendencias.aplicacao import JaResolvida, Pendencias, SemPendencia, SemPermissao
from modules.orchestration.pendencias.repositorio import SqlAlchemyPendencias

router = APIRouter(prefix="/pendencias", tags=["orchestration"])


def enfileirar_continuacao(db: Session) -> Any:
    """Uma execução nova só com os itens: o cadastro atual do item quando existe (o que a pessoa
    acabou de ajustar), senão o retrato do pedido original; os mesmos campos de entrada."""
    from sqlalchemy import select

    from modules.catalog.domain.itens import configuracao_de_trabalho
    from modules.catalog.infrastructure.orm.models import CatalogAutomationVersionRecord
    from modules.catalog.infrastructure.repositories.sqlalchemy_itens import SqlAlchemyItemRegistry
    from modules.dispatch.api.fila import _mudou
    from modules.dispatch.infrastructure.adapters.fila import build_fila
    from modules.orchestration.application.use_cases.queue import FilaError

    def enfileirar(automation_id: int, execucao_original: str, chaves: list[str], solicitante: str) -> dict[str, Any]:
        repo = SqlAlchemyPendencias(db)
        original = repo.execucao(execucao_original) or {}
        parametros = dict((original.get("input") or {}).get("parametros") or {})
        retrato = repo.itens_do_pedido(execucao_original)
        registro = SqlAlchemyItemRegistry(db)
        spec = registro.spec(automation_id)
        atuais = {r.chave: r for r in registro.selecionar(automation_id, chaves, False)} if spec is not None else {}
        itens = []
        for chave in chaves:
            if chave in atuais:
                r = atuais[chave]
                itens.append({"chave": r.chave, "rotulo": r.rotulo, "grupo": r.grupo_chave or r.chave, "atributos": dict(r.atributos or {}),
                              "configuracao": configuracao_de_trabalho(spec, dict(r.atributos or {}))})
            elif chave in retrato:
                antigo = retrato[chave]
                itens.append({k: antigo.get(k) for k in ("chave", "rotulo", "grupo", "atributos", "configuracao")})
            else:
                itens.append({"chave": chave, "rotulo": chave, "grupo": chave, "atributos": {}, "configuracao": {}})
        versao = db.scalar(select(CatalogAutomationVersionRecord.id).where(
            CatalogAutomationVersionRecord.automation_id == automation_id, CatalogAutomationVersionRecord.status == "published")
            .order_by(CatalogAutomationVersionRecord.id.desc()).limit(1))
        if versao is None:
            raise HTTPException(status_code=422, detail="A automação não tem versão publicada.")
        fila = build_fila(db)
        try:
            resultado = fila.enfileirar.execute(automation_version_id=versao, itens=itens, parametros=parametros, prioridade=0,
                                                solicitante=solicitante, now=datetime.now(UTC), origem="pendencia")
        except FilaError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        fila.transaction.commit()
        _mudou()
        return resultado

    return enfileirar


def pedir_email_do_portal(db: Session) -> Any:
    from modules.telemetry.correio.api import build_correio
    from modules.telemetry.correio.correio import Contexto, validar

    def pedir(para: list[str], assunto: str, corpo_html: str, execution_id: str, automation_id: int) -> Any:
        mensagem = validar({"para": para, "assunto": assunto, "html": corpo_html})
        return build_correio(db).pedir(Contexto(origem="portal", tipo="pendencia", automation_id=automation_id,
                                                execution_id=execution_id), mensagem)

    return pedir


def pendencias(db: Session) -> Pendencias:
    from modules.governance.infrastructure.adapters import build_governance_adapters

    acesso = acesso_por_automacao(db)
    return Pendencias(SqlAlchemyPendencias(db), lambda user, aid, acao: acesso.pode(user, aid, acao), enfileirar_continuacao(db),
                      pedir_email_do_portal(db), get_settings().frontend_url, build_governance_adapters(db).audit)


def _fazer(db: Session, acao: Any) -> Any:
    try:
        resultado = acao()
        db.commit()
        return resultado
    except SemPendencia as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SemPermissao as exc:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except JaResolvida as exc:
        db.rollback()
        return JSONResponse(status_code=409, content=jsonable_encoder({"erro": str(exc), "resolucao": exc.resolucao}))


@router.get("")
def listar(db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    return {"execucoes": _fazer(db, lambda: pendencias(db).listar(user))}


@router.get("/avisos/{aviso_id}")
def ver_aviso(aviso_id: str, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> Any:
    return _fazer(db, lambda: pendencias(db).aviso(user, aviso_id))


@router.post("/avisos/{aviso_id}/continuar")
def continuar_pelo_aviso(aviso_id: str, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> Any:
    return _fazer(db, lambda: pendencias(db).continuar(user, aviso_id=aviso_id, via="email"))


@router.get("/execucoes/{execution_id}")
def da_execucao(execution_id: str, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> Any:
    return _fazer(db, lambda: pendencias(db).da_execucao(user, execution_id))


@router.post("/execucoes/{execution_id}/continuar")
def continuar_pela_execucao(execution_id: str, corpo: dict[str, Any] = Body(default={}), db: Session = Depends(get_db),
                            user: Any = Depends(get_current_user)) -> Any:
    itens = corpo.get("itens")
    if itens is not None and (not isinstance(itens, list) or not all(isinstance(i, str) for i in itens)):
        raise HTTPException(status_code=422, detail="itens: lista de chaves.")
    return _fazer(db, lambda: pendencias(db).continuar(user, execution_id=execution_id, itens=itens, via="portal"))
