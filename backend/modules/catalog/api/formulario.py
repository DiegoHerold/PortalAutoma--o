"""Campos da automação (Fase 7): ver e editar o que se informa ao acionar e o que cada item guarda.

Ver: ``executar`` ou ``editar_itens``. Editar: ``editar_itens`` (admin e gestor têm por
padrão), sempre com auditoria do antes e do depois. ``versao`` evita que duas pessoas
gravem por cima uma da outra.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from infrastructure.database import get_db
from modules.access.api.authorization import acesso_por_automacao, ensure_automation_grant
from modules.access.api.dependencies import get_current_user
from modules.access.domain.concessao import EDITAR_ITENS, EXECUTAR
from modules.catalog.domain.formulario import TIPOS, FormularioInvalido, validar_campos
from modules.catalog.infrastructure.repositories.sqlalchemy_itens import SqlAlchemyItemRegistry
from modules.governance.domain.audit import AuditEvent
from modules.governance.infrastructure.adapters import build_governance_adapters

router = APIRouter(prefix="/automations/{automation_id}/formulario", tags=["catalog"])

ROTULOS_DOS_TIPOS = {
    "texto": "Texto", "texto_longo": "Texto longo", "numero": "Número", "inteiro": "Número inteiro",
    "sim_nao": "Sim ou não", "data": "Data", "mes_ano": "Mês/ano", "lista": "Lista de opções",
    "email": "E-mail", "pasta": "Pasta", "json": "Dados avançados (JSON)",
}


def _resposta(db: Session, user: Any, automation_id: int) -> dict[str, Any]:
    registro = SqlAlchemyItemRegistry(db)
    form = registro.formulario(automation_id)
    spec = registro.spec_do_manifesto(automation_id)
    return {
        "origem": form.origem, "versao": registro.versao_do_formulario(automation_id),
        "pode_editar": acesso_por_automacao(db).pode(user, automation_id, EDITAR_ITENS),
        "item": None if spec is None else {"nome": spec.label, "chave": spec.key, "grupo": spec.group_attribute},
        "entrada": [c.publico() for c in form.entrada],
        "colunas": [c.publico() for c in form.colunas],
        "tipos": [{"tipo": t, "rotulo": ROTULOS_DOS_TIPOS[t]} for t in TIPOS],
    }


@router.get("")
def ver(automation_id: int, db: Session = Depends(get_db), user: Any = Depends(get_current_user)) -> dict[str, Any]:
    if not acesso_por_automacao(db).pode(user, automation_id, EDITAR_ITENS):
        ensure_automation_grant(db, user, automation_id, EXECUTAR)
    return _resposta(db, user, automation_id)


@router.put("")
def gravar(automation_id: int, corpo: dict[str, Any] = Body(...), db: Session = Depends(get_db),
           user: Any = Depends(get_current_user)) -> dict[str, Any]:
    ensure_automation_grant(db, user, automation_id, EDITAR_ITENS)
    registro = SqlAlchemyItemRegistry(db)
    atual = registro.versao_do_formulario(automation_id)
    if corpo.get("versao") is not None and int(corpo["versao"]) != atual:
        raise HTTPException(status_code=409, detail="Outra pessoa mudou os campos agora há pouco. Recarregue e refaça.")
    erros: dict[str, str] = {}
    listas = {}
    for nome in ("entrada", "colunas"):
        try:
            listas[nome] = validar_campos(corpo.get(nome) if corpo.get(nome) is not None else [])
        except FormularioInvalido as exc:
            erros.update({f"{nome}.{k}": v for k, v in exc.campos.items()})
    if erros:
        raise HTTPException(status_code=422, detail={"campos": erros})
    antes = registro.formulario(automation_id)
    versao = registro.gravar_formulario(automation_id, listas["entrada"], listas["colunas"],
                                        str(getattr(user, "id", "")) or "desconhecido")
    build_governance_adapters(db).audit.append(AuditEvent(
        id=f"aud_{uuid4().hex}", actor_type="user", actor_id=str(getattr(user, "id", "")) or None,
        action="automacao.campos.alterados", resource_type="automation", resource_id=str(automation_id),
        before={"entrada": [c.publico() for c in antes.entrada], "colunas": [c.publico() for c in antes.colunas],
                "origem": antes.origem},
        after={"entrada": [c.publico() for c in listas["entrada"]], "colunas": [c.publico() for c in listas["colunas"]],
               "versao": versao},
        occurred_at=datetime.now(UTC)))
    db.commit()
    return _resposta(db, user, automation_id)
