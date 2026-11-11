"""Administração das instâncias diretas e do cadastro de máquinas (admin ou gestor)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from infrastructure.database import get_db
from modules.access.api.dependencies import get_current_user
from modules.access.application.use_cases import PermissionChecker
from modules.access.domain import AuthorizationDenied
from modules.access.infrastructure.adapters import build_access_adapters
from modules.fleet.application.use_cases.instancias_diretas import DecidirInstancia, GerarCodigoDeInscricao
from modules.fleet.domain.instancia_direta import TransicaoInvalida
from modules.fleet.infrastructure.repositories.sqlalchemy_direct_instances import (
    SqlAlchemyDirectInstanceStore,
    SqlAlchemyMachineStore,
)
from modules.governance.domain.audit import AuditEvent
from modules.governance.infrastructure.adapters import build_governance_adapters

router = APIRouter(tags=["fleet"])


def _gestor(db: Session, user: Any) -> str:
    try:
        PermissionChecker(build_access_adapters(db).access).ensure_admin_or_manager(user)
    except AuthorizationDenied as exc:
        raise HTTPException(status_code=403, detail="Só administrador ou gestor.") from exc
    return str(getattr(user, "id", "")) or "desconhecido"


@router.post("/automations/{automation_id}/instancias-diretas/codigos", status_code=201)
def gerar_codigo(automation_id: int, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    """Código de uso único, válido por 30 minutos, mostrado uma vez só."""
    por = _gestor(db, user)
    if build_access_adapters(db).access.get_automation_category_id(automation_id) is None:
        raise HTTPException(status_code=404, detail="Automação não encontrada.")
    codigo, expira = GerarCodigoDeInscricao(SqlAlchemyDirectInstanceStore(db), build_governance_adapters(db).audit,
                                            db).execute(automation_id=automation_id, por=por, agora=datetime.now(UTC))
    return {"codigo": codigo, "expira_em": expira.isoformat()}


@router.get("/automations/{automation_id}/instancias-diretas")
def listar(automation_id: int, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    _gestor(db, user)
    return {"instancias": SqlAlchemyDirectInstanceStore(db).da_automacao(automation_id)}


@router.get("/instancias-diretas")
def todas(db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    _gestor(db, user)
    return {"instancias": SqlAlchemyDirectInstanceStore(db).todas()}


@router.post("/instancias-diretas/{instancia_id}/{acao}")
def decidir(instancia_id: str, acao: str, corpo: dict[str, Any] = Body(default={}), db: Session = Depends(get_db),
            user: Any = Depends(get_current_user)) -> dict[str, Any]:
    """``aprovar`` (com ``maquina_id``), ``quarentena`` ou ``revogar``."""
    por = _gestor(db, user)
    try:
        return DecidirInstancia(SqlAlchemyDirectInstanceStore(db), build_governance_adapters(db).audit, db).execute(
            instancia_id=instancia_id, acao=acao, por=por, agora=datetime.now(UTC), maquina=corpo.get("maquina_id"))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TransicaoInvalida as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/maquinas")
def listar_maquinas(db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    _gestor(db, user)
    return {"maquinas": SqlAlchemyMachineStore(db).listar()}


@router.post("/maquinas", status_code=201)
def cadastrar_maquina(corpo: dict[str, Any] = Body(...), db: Session = Depends(get_db),
                      user: Any = Depends(get_current_user)) -> dict[str, Any]:
    """Máquina sem Agent (ADR-019): o administrador cadastra e depois aprova instâncias nela."""
    por = _gestor(db, user)
    nome = str(corpo.get("nome") or "").strip()
    if not 2 <= len(nome) <= 120:
        raise HTTPException(status_code=422, detail="Informe o nome da máquina (2 a 120 caracteres).")
    maquinas = SqlAlchemyMachineStore(db)
    if maquinas.nome_em_uso(nome):
        raise HTTPException(status_code=409, detail="Já existe uma máquina ativa com esse nome.")
    machine_id = f"mch_{uuid4().hex[:12]}"
    maquinas.adicionar(machine_id=machine_id, nome=nome)
    build_governance_adapters(db).audit.append(AuditEvent(
        id=f"aud_{uuid4().hex}", actor_type="user", actor_id=por, action="maquina.cadastrada", resource_type="machine",
        resource_id=machine_id, after={"nome": nome}, occurred_at=datetime.now(UTC)))
    db.commit()
    return {"id": machine_id, "nome": nome}
