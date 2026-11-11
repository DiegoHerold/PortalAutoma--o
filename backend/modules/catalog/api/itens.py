"""Cadastro de itens por automação e o pedido de execução a partir dele (Fase 5).

Ver a lista: ``executar`` ou ``editar_itens``. Atributos (e-mails, pastas de clientes): só
com ``editar_itens``. Mudar e importar: ``editar_itens``, sempre com auditoria.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from infrastructure.database import get_db
from modules.access.api.authorization import acesso_por_automacao, ensure_automation_grant
from modules.access.api.dependencies import get_current_user
from modules.access.domain.concessao import EDITAR_ITENS, EXECUTAR
from modules.catalog.domain.formulario import FormularioInvalido, valores
from modules.catalog.domain.itens import ItemInvalido, configuracao_de_trabalho, conferir_grupos, previa, validar
from modules.catalog.infrastructure.orm.models import CatalogAutomationVersionRecord
from modules.catalog.infrastructure.repositories.sqlalchemy_itens import SqlAlchemyItemRegistry, ler_empresas_db
from modules.governance.domain.audit import AuditEvent
from modules.governance.infrastructure.adapters import build_governance_adapters

router = APIRouter(prefix="/automations/{automation_id}/itens", tags=["catalog"])

LIMITE_ARQUIVO = 20 * 1024 * 1024


def _agora() -> datetime:
    return datetime.now(UTC)


def _quem(user: Any) -> str:
    return str(getattr(user, "id", "")) or "desconhecido"


def _auditar(db: Session, user: Any, acao: str, automation_id: int, chave: str, antes: Any, depois: Any) -> None:
    build_governance_adapters(db).audit.append(AuditEvent(
        id=f"aud_{uuid4().hex}", actor_type="user", actor_id=_quem(user), action=acao, resource_type="automation_item",
        resource_id=f"{automation_id}:{chave}", before=antes, after=depois, occurred_at=_agora()))


def _pode_editar(db: Session, user: Any, automation_id: int) -> bool:
    return acesso_por_automacao(db).pode(user, automation_id, EDITAR_ITENS)


def _definicao(spec: Any) -> dict[str, Any] | None:
    if spec is None:
        return None
    return {"nome": spec.label, "chave": spec.key, "grupo": spec.group_attribute,
            "atributos": spec.attributes_schema or {}, "afetam_trabalho": list(spec.work_attributes)}


@router.get("")
def listar(automation_id: int, busca: str | None = Query(default=None, max_length=120), ativos: bool | None = None,
           limite: int = Query(default=100, ge=1, le=500), pular: int = Query(default=0, ge=0),
           db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    editar = _pode_editar(db, user, automation_id)
    if not editar:
        ensure_automation_grant(db, user, automation_id, EXECUTAR)
    registro = SqlAlchemyItemRegistry(db)
    itens = registro.listar(automation_id, busca=busca, ativos=ativos, limite=limite, pular=pular)
    if not editar:
        for item in itens:
            item["atributos"] = {}  # e-mails e pastas de clientes: só quem edita vê
    return {"definicao": _definicao(registro.spec(automation_id)), "pode_editar": editar,
            "contagem": registro.contar(automation_id), "itens": itens,
            "proximo": pular + limite if len(itens) == limite else None}


@router.post("", status_code=201)
def criar(automation_id: int, corpo: dict[str, Any] = Body(...), db: Session = Depends(get_db),
          user: Any = Depends(get_current_user)) -> dict[str, Any]:
    return _gravar(db, user, automation_id, corpo, nova=True)


@router.put("/{chave}")
def alterar(automation_id: int, chave: str, corpo: dict[str, Any] = Body(...), db: Session = Depends(get_db),
            user: Any = Depends(get_current_user)) -> dict[str, Any]:
    return _gravar(db, user, automation_id, {**corpo, "chave": chave}, nova=False)


@router.post("/{chave}/situacao")
def situacao(automation_id: int, chave: str, corpo: dict[str, Any] = Body(...), db: Session = Depends(get_db),
             user: Any = Depends(get_current_user)) -> dict[str, Any]:
    ensure_automation_grant(db, user, automation_id, EDITAR_ITENS)
    registro = SqlAlchemyItemRegistry(db).obter(automation_id, chave)
    if registro is None:
        raise HTTPException(status_code=404, detail="Item não encontrado.")
    antes = registro.ativo
    registro.ativo, registro.updated_by, registro.updated_at = bool(corpo.get("ativo")), _quem(user), _agora()
    _auditar(db, user, "automacao.item.situacao", automation_id, chave, {"ativo": antes}, {"ativo": registro.ativo})
    db.commit()
    return {"chave": chave, "ativo": registro.ativo}


def _gravar(db: Session, user: Any, automation_id: int, corpo: dict[str, Any], *, nova: bool) -> dict[str, Any]:
    ensure_automation_grant(db, user, automation_id, EDITAR_ITENS)
    registro = SqlAlchemyItemRegistry(db)
    existente = registro.obter(automation_id, str(corpo.get("chave") or ""))
    if nova and existente is not None:
        raise HTTPException(status_code=409, detail="Já existe um item com essa chave.")
    if not nova and existente is None:
        raise HTTPException(status_code=404, detail="Item não encontrado.")
    form = registro.formulario(automation_id)
    if form.origem == "portal":  # colunas editadas no Portal: padrão, obrigatório e tipo (Fase 7)
        try:
            corpo = {**corpo, "atributos": valores(form.colunas, corpo.get("atributos") or {}, manter_extras=True)}
        except FormularioInvalido as exc:
            raise HTTPException(status_code=422, detail={"campos": {f"atributos.{k}": v for k, v in exc.campos.items()}}) from exc
    try:
        item = validar(registro.spec(automation_id), {**corpo, "ativo": corpo.get("ativo", existente.ativo if existente else True)})
    except ItemInvalido as exc:
        raise HTTPException(status_code=422, detail={"campos": exc.campos}) from exc
    problemas = conferir_grupos({**registro.todos(automation_id), item.chave: item})
    if item.chave in problemas:
        raise HTTPException(status_code=422, detail={"campos": {"grupo": problemas[item.chave]}})
    gravado, antes = registro.gravar(automation_id, item, por=_quem(user), agora=_agora())
    _auditar(db, user, "automacao.item.criado" if nova else "automacao.item.alterado", automation_id, item.chave, antes,
             {"rotulo": item.rotulo, "grupo": item.grupo, "atributos": item.atributos, "ativo": item.ativo})
    db.commit()
    return {"chave": gravado.chave, "rotulo": gravado.rotulo, "grupo": gravado.grupo_chave,
            "atributos": dict(gravado.atributos or {}), "ativo": gravado.ativo}


@router.post("/importar/previa")
async def importar_previa(automation_id: int, arquivo: UploadFile = File(...), db: Session = Depends(get_db),
                          user: Any = Depends(get_current_user)) -> dict[str, Any]:
    """``empresas.db`` da Integração Contábil: o que seria criado e alterado, sem gravar."""
    ensure_automation_grant(db, user, automation_id, EDITAR_ITENS)
    conteudo = await arquivo.read(LIMITE_ARQUIVO + 1)
    if len(conteudo) > LIMITE_ARQUIVO:
        raise HTTPException(status_code=413, detail="Arquivo acima de 20 MB.")
    try:
        vindos = ler_empresas_db(conteudo)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    registro = SqlAlchemyItemRegistry(db)
    return previa(registro.todos(automation_id), vindos, registro.spec(automation_id))


@router.post("/importar")
def importar(automation_id: int, corpo: dict[str, Any] = Body(...), db: Session = Depends(get_db),
             user: Any = Depends(get_current_user)) -> dict[str, Any]:
    """Grava as linhas escolhidas na prévia. Confere tudo de novo: o que vem do navegador não é confiável."""
    ensure_automation_grant(db, user, automation_id, EDITAR_ITENS)
    linhas = corpo.get("itens")
    if not isinstance(linhas, list) or not 1 <= len(linhas) <= 5000:
        raise HTTPException(status_code=422, detail="Envie de 1 a 5000 itens.")
    registro = SqlAlchemyItemRegistry(db)
    resultado = previa(registro.todos(automation_id), linhas, registro.spec(automation_id))
    if resultado["erros"]:
        raise HTTPException(status_code=422, detail={"erros": resultado["erros"]})
    spec, agora, por = registro.spec(automation_id), _agora(), _quem(user)
    for bruto in resultado["novos"] + resultado["alterados"]:
        item = validar(spec, bruto)
        _, antes = registro.gravar(automation_id, item, por=por, agora=agora)
        _auditar(db, user, "automacao.item.importado", automation_id, item.chave, antes,
                 {"rotulo": item.rotulo, "grupo": item.grupo, "ativo": item.ativo})
    db.commit()
    return {"criados": len(resultado["novos"]), "alterados": len(resultado["alterados"]), "iguais": resultado["iguais"]}


@router.post("/pedir-execucao", status_code=201)
def pedir_execucao(automation_id: int, corpo: dict[str, Any] = Body(...), db: Session = Depends(get_db),
                   user: Any = Depends(get_current_user)) -> dict[str, Any]:
    """Itens escolhidos do cadastro (com as filiais, se pedido) -> fila, com a versão publicada mais recente."""
    from modules.dispatch.api.fila import _mudou
    from modules.dispatch.infrastructure.adapters.fila import build_fila
    from modules.orchestration.application.use_cases.queue import FilaError

    ensure_automation_grant(db, user, automation_id, EXECUTAR)
    from modules.catalog.infrastructure.orm.models import CatalogAutomationRecord

    automacao = db.get(CatalogAutomationRecord, automation_id)
    if automacao is not None and (automacao.status == "archived" or not automacao.is_active):
        raise HTTPException(status_code=422, detail="A automação está arquivada: restaure no Catálogo para executar.")
    registro = SqlAlchemyItemRegistry(db)
    spec = registro.spec(automation_id)
    chaves = corpo.get("chaves") or []
    # Automação sem itens (ex.: uma conferência geral) roda sem escolher nada.
    minimo = 0 if spec is None else 1
    if not isinstance(chaves, list) or not minimo <= len(chaves) <= 2000:
        raise HTTPException(status_code=422, detail="Escolha de 1 a 2000 itens.")
    form = registro.formulario(automation_id)
    recebidos = corpo.get("parametros") or {}
    if not isinstance(recebidos, dict) or len(str(recebidos)) > 64 * 1024:
        raise HTTPException(status_code=422, detail="parametros: envie um objeto de até 64 KB.")
    if form.entrada or form.origem == "portal":
        try:  # as informações do pedido, conferidas pelos campos da automação (Fase 7)
            parametros = valores(form.entrada, recebidos)
        except FormularioInvalido as exc:
            raise HTTPException(status_code=422, detail={"campos": exc.campos}) from exc
    else:
        parametros = recebidos  # automação sem nenhum campo definido ainda: como antes da Fase 7
    escolhidos = registro.selecionar(automation_id, [str(c) for c in chaves], bool(corpo.get("com_filiais", True))) if chaves else []
    if chaves and not escolhidos:
        raise HTTPException(status_code=422, detail="Nenhum item ativo com essas chaves.")
    versao = db.scalar(select(CatalogAutomationVersionRecord.id)
                       .where(CatalogAutomationVersionRecord.automation_id == automation_id,
                              CatalogAutomationVersionRecord.status == "published")
                       .order_by(CatalogAutomationVersionRecord.id.desc()).limit(1))
    if versao is None:
        raise HTTPException(status_code=422, detail="A automação não tem versão publicada.")
    itens = [{"chave": r.chave, "rotulo": r.rotulo, "grupo": r.grupo_chave or r.chave, "atributos": dict(r.atributos or {}),
              "configuracao": configuracao_de_trabalho(spec, dict(r.atributos or {}))} for r in escolhidos]
    fila = build_fila(db)
    try:
        resultado = fila.enfileirar.execute(automation_version_id=versao, itens=itens,
                                            parametros=parametros,
                                            prioridade=int(corpo.get("prioridade") or 0), solicitante=_quem(user), now=_agora())
    except FilaError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    fila.transaction.commit()
    _mudou()
    return {**resultado, "itens": [i["chave"] for i in itens]}
