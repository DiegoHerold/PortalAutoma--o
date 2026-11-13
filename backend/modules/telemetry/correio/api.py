"""API dos e-mails (13/11/2026). Regras em ``correio.py``.

- ``GET /emails``: os e-mails (filtros: situacao, automacao, busca, antes) e o resumo das 24 h.
- ``GET /emails/configuracao``: se o envio está ligado, o remetente e os domínios permitidos.
- ``GET /emails/{id}``: o e-mail com o corpo e os anexos (nomes).
- ``POST /emails/{id}/reenviar``, ``POST /emails/dominios``, ``DELETE /emails/dominios/{dominio}``,
  ``POST /emails/teste``: ``emails.gerenciar``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from infrastructure.config import get_settings
from infrastructure.database import get_db
from modules.access.api.authorization import precisa
from modules.access.api.dependencies import get_current_user
from modules.telemetry.correio.correio import Contexto, Correio, EmailInvalido, validar
from modules.telemetry.correio.repositorio import SqlAlchemyCorreio

router = APIRouter(prefix="/emails", tags=["telemetry"])

VER = [Depends(precisa("emails.ver", "emails.gerenciar"))]
GERENCIAR = [Depends(precisa("emails.gerenciar"))]


def build_correio(db: Session) -> Correio:
    from modules.telemetry.infrastructure.email_graph import montar_carteiro

    settings = get_settings()
    return Correio(SqlAlchemyCorreio(db), montar_carteiro(settings), settings.graph_remetente)


def resumo_do_email(registro: Any, nomes: dict[int, str], anexos: list[Any]) -> dict[str, Any]:
    return {"id": registro.id, "origem": registro.origem, "tipo": registro.tipo,
            "automacao": {"id": registro.automation_id, "nome": nomes.get(registro.automation_id)} if registro.automation_id else None,
            "execucao_id": registro.execution_id, "para": registro.para, "cc": registro.cc, "cco": registro.cco,
            "assunto": registro.assunto, "situacao": registro.situacao, "motivo": registro.motivo, "meio": registro.meio,
            "tentativas": registro.tentativas, "proxima_tentativa_em": registro.proxima_tentativa_em,
            "criado_em": registro.criado_em, "enviado_em": registro.enviado_em,
            "anexos": [{"nome": a.nome, "tamanho": a.tamanho} for a in anexos]}


def _fazer(db: Session, acao: Any) -> Any:
    try:
        resultado = acao()
        db.commit()
        return resultado
    except EmailInvalido as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("", dependencies=VER)
def listar(situacao: str | None = None, automacao: int | None = None, busca: str | None = Query(default=None, max_length=120),
           antes: datetime | None = None, limite: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db)) -> dict[str, Any]:
    repo = SqlAlchemyCorreio(db)
    lista = repo.lista(situacao=situacao, automation_id=automacao, busca=busca, antes=antes, limite=limite)
    nomes = repo.nomes_das_automacoes({e.automation_id for e in lista if e.automation_id})
    return {"emails": [resumo_do_email(e, nomes, repo.anexos(e.id)) for e in lista],
            "resumo_24h": repo.contagem_por_situacao(datetime.now(UTC) - timedelta(hours=24)),
            "cursor": lista[-1].criado_em if len(lista) == limite else None}


@router.get("/configuracao", dependencies=VER)
def configuracao(db: Session = Depends(get_db)) -> dict[str, Any]:
    from modules.telemetry.infrastructure.email_graph import situacao_do_envio

    correio = build_correio(db)
    return {"situacao": situacao_do_envio(get_settings()), "remetente": get_settings().graph_remetente or None,
            "dominio_do_remetente": correio.dominio_do_remetente(), "dominios": correio.dominios()}


@router.post("/dominios", status_code=201, dependencies=GERENCIAR)
def adicionar_dominio(corpo: dict[str, Any] = Body(...), db: Session = Depends(get_db),
                      user: Any = Depends(get_current_user)) -> dict[str, Any]:
    return {"dominio": _fazer(db, lambda: build_correio(db).adicionar_dominio(corpo.get("dominio"), str(getattr(user, "id", ""))))}


@router.delete("/dominios/{dominio}", status_code=204, response_model=None, response_class=Response, dependencies=GERENCIAR)
def remover_dominio(dominio: str, db: Session = Depends(get_db)) -> None:
    _fazer(db, lambda: build_correio(db).remover_dominio(dominio))


@router.post("/teste", dependencies=GERENCIAR)
def teste(corpo: dict[str, Any] = Body(default={}), db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    para = corpo.get("para") or getattr(user, "email", None)

    def mandar() -> Any:
        mensagem = validar({"para": [para] if isinstance(para, str) else para, "assunto": "Teste de e-mail do Portal de Automações",
                            "html": "<p>Se você recebeu esta mensagem, o envio de e-mail do Portal está funcionando.</p>"})
        return build_correio(db).pedir(Contexto(origem="portal", tipo="teste", criado_por=str(getattr(user, "id", ""))), mensagem)

    registro = _fazer(db, mandar)
    return {"id": registro.id, "situacao": registro.situacao, "motivo": registro.motivo}


@router.get("/{email_id}", dependencies=VER)
def ver(email_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    repo = SqlAlchemyCorreio(db)
    registro = repo.email(email_id)
    if registro is None:
        raise HTTPException(status_code=404, detail="E-mail não encontrado.")
    nomes = repo.nomes_das_automacoes({registro.automation_id} if registro.automation_id else set())
    return {"email": {**resumo_do_email(registro, nomes, repo.anexos(registro.id)), "html": registro.html, "texto": registro.texto}}


@router.post("/{email_id}/reenviar", dependencies=GERENCIAR)
def reenviar(email_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    registro = _fazer(db, lambda: build_correio(db).reenviar(email_id))
    return {"id": registro.id, "situacao": registro.situacao, "motivo": registro.motivo}
