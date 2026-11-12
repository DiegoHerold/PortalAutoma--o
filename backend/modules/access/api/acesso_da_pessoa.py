"""O que uma pessoa acessa, num lugar só (12/11/2026, etapa 3).

- ``GET /acesso/pessoas``: os times de cada pessoa (para a lista de Usuários).
- ``GET /acesso/pessoas/{id}``: o resumo: as **telas** (pelo papel), as **automações** (pelos times)
  e as **exceções** (concessões direto na pessoa, na aba Acessos da automação).

Só leitura; quem tem a funcionalidade Usuários vê.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from infrastructure.database import get_db
from modules.access.api.authorization import precisa
from modules.access.application.papeis import tabela_do_papel
from modules.access.domain.funcionalidades import POR_CHAVE
from modules.access.infrastructure.orm.models import (
    AccessCategoryRecord,
    AccessTeamRecord,
    AccessUserCategoryPermissionRecord,
    AccessUserRecord,
    AutomationGrantRecord,
    TeamCategoryPermissionRecord,
    TeamMembershipRecord,
)
from modules.access.infrastructure.repositories.sqlalchemy_papeis import SqlAlchemyPapeis

router = APIRouter(prefix="/acesso", tags=["access"])


def _automacoes(db: Session, ids: set[int]) -> dict[int, str]:
    from modules.catalog.infrastructure.orm.models import CatalogAutomationRecord

    if not ids:
        return {}
    return dict(db.execute(select(CatalogAutomationRecord.id, CatalogAutomationRecord.name)
                           .where(CatalogAutomationRecord.id.in_(ids))).all())


@router.get("/pessoas", dependencies=[Depends(precisa("usuarios.ver"))])
def times_das_pessoas(db: Session = Depends(get_db)) -> dict[str, Any]:
    saida: dict[str, list[dict[str, Any]]] = {}
    for user_id, team_id, nome, situacao in db.execute(
        select(TeamMembershipRecord.user_id, AccessTeamRecord.id, AccessTeamRecord.name, AccessTeamRecord.status)
        .join(AccessTeamRecord, AccessTeamRecord.id == TeamMembershipRecord.team_id).order_by(AccessTeamRecord.name)
    ):
        saida.setdefault(str(user_id), []).append({"id": team_id, "nome": nome, "ativo": situacao == "active"})
    return {"times": saida}


@router.get("/pessoas/{user_id}", dependencies=[Depends(precisa("usuarios.ver"))])
def acesso_da_pessoa(user_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    pessoa = db.get(AccessUserRecord, user_id)
    if pessoa is None:
        raise HTTPException(status_code=404, detail="Pessoa não encontrada.")

    papel = SqlAlchemyPapeis(db).obter(pessoa.role_id)
    tabela = tabela_do_papel(papel) if papel else {}
    telas = [{"chave": f, "nome": POR_CHAVE[f].nome, "grupo": POR_CHAVE[f].grupo, "nivel": n}
             for f, n in tabela.items() if f in POR_CHAVE]

    times = []
    for time in db.scalars(select(AccessTeamRecord).join(TeamMembershipRecord, TeamMembershipRecord.team_id == AccessTeamRecord.id)
                           .where(TeamMembershipRecord.user_id == user_id).order_by(AccessTeamRecord.name)):
        categorias = [{"categoria": nome, "ver": p.can_view, "executar": p.can_execute,
                       "editar": p.can_create or p.can_edit or p.can_delete, "publicar": p.can_approve}
                      for p, nome in db.execute(
                          select(TeamCategoryPermissionRecord, AccessCategoryRecord.name)
                          .join(AccessCategoryRecord, AccessCategoryRecord.id == TeamCategoryPermissionRecord.category_id)
                          .where(TeamCategoryPermissionRecord.team_id == time.id).order_by(AccessCategoryRecord.name))]
        concessoes = list(db.scalars(select(AutomationGrantRecord).where(AutomationGrantRecord.team_id == time.id)))
        nomes = _automacoes(db, {c.automation_id for c in concessoes})
        times.append({"id": time.id, "nome": time.name, "ativo": time.status == "active", "categorias": categorias,
                      "automacoes": [{"automation_id": c.automation_id, "automacao": nomes.get(c.automation_id),
                                      "acoes": list(c.acoes or [])} for c in concessoes]})

    proprias = list(db.scalars(select(AutomationGrantRecord).where(AutomationGrantRecord.user_id == user_id)))
    nomes = _automacoes(db, {c.automation_id for c in proprias})
    soltas = db.scalar(select(AccessUserCategoryPermissionRecord.id)
                       .where(AccessUserCategoryPermissionRecord.user_id == user_id).limit(1)) is not None
    return {
        "pessoa": {"id": pessoa.id, "nome": pessoa.name, "email": pessoa.email},
        "papel": {"id": papel["id"], "nome": papel["nome"], "slug": papel["slug"], "telas": telas} if papel else None,
        "times": times,
        "excecoes": [{"automation_id": c.automation_id, "automacao": nomes.get(c.automation_id), "acoes": list(c.acoes or [])}
                     for c in proprias],
        # Permissões por categoria ainda soltas na pessoa (deveria ser falso depois da etapa 2).
        "permissoes_soltas": soltas,
    }
