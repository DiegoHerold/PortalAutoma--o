"""Consultas da tela de Auditoria (12/11/2026): a linha do tempo com filtros, os grupos com contagem
(por dia, por pessoa ou por ação) e as pessoas que aparecem. Só lê."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import and_, exists, func, literal, not_, or_, select
from sqlalchemy.orm import Session, aliased

from modules.governance.domain.auditoria import ACESSO_EXATO, ACESSO_PREFIXOS, EXECUCAO_PREFIXOS, FUSO, tipo_do_evento
from modules.governance.infrastructure.orm.models import AuditEventRecord as E


@dataclass(frozen=True)
class Filtros:
    de: datetime | None = None
    ate: datetime | None = None
    usuario: str | None = None
    usuario_email: str | None = None  # logins antigos guardavam o e-mail no lugar do número
    tipo: str | None = None
    acao: str | None = None
    recurso_tipo: str | None = None
    recurso_id: str | None = None
    correlacao: str | None = None
    busca: str | None = None
    tecnicos: bool = False  # mostra também o registro técnico da requisição quando há o evento de negócio


def _comeca(coluna: Any, prefixos: tuple[str, ...]) -> Any:
    return or_(*[coluna.like(f"{p}%") for p in prefixos])


def _condicao_do_tipo(tipo: str) -> Any:
    acesso = or_(E.action.in_(ACESSO_EXATO), _comeca(E.action, ACESSO_PREFIXOS))
    execucao = _comeca(E.action, EXECUCAO_PREFIXOS)
    if tipo == "acesso":
        return acesso
    if tipo == "execucao":
        return and_(not_(acesso), execucao)
    if tipo == "sistema":
        return and_(not_(acesso), not_(execucao), E.actor_type != "user")
    return and_(not_(acesso), not_(execucao), E.actor_type == "user")


def _onde(f: Filtros) -> list[Any]:
    condicoes: list[Any] = []
    if f.de:
        condicoes.append(E.occurred_at >= f.de)
    if f.ate:
        condicoes.append(E.occurred_at < f.ate)
    if f.usuario:
        condicoes.append(E.actor_id.in_([f.usuario, f.usuario_email]) if f.usuario_email else E.actor_id == f.usuario)
    if f.tipo:
        condicoes.append(_condicao_do_tipo(f.tipo))
    if f.acao:
        condicoes.append(E.action == f.acao)
    if f.recurso_tipo:
        condicoes.append(E.resource_type == f.recurso_tipo)
    if f.recurso_id:
        condicoes.append(E.resource_id == f.recurso_id)
    if f.correlacao:
        condicoes.append(E.correlation_id == f.correlacao)
    if f.busca and f.busca.strip():
        padrao = f"%{f.busca.strip()}%"
        condicoes.append(or_(E.action.ilike(padrao), E.resource_type.ilike(padrao), E.resource_id.ilike(padrao),
                             E.actor_id.ilike(padrao)))
    if not f.tecnicos and not f.acao:
        # Telas abertas (registradas até 12/11/2026) não aparecem na linha do tempo normal.
        condicoes.append(E.action != "tela.aberta")
    if not f.tecnicos and not f.correlacao:
        # O registro técnico (api.*) some quando a mesma requisição gravou o evento de negócio.
        outro = aliased(E)
        condicoes.append(not_(and_(E.action.like("api.%"), exists().where(
            outro.correlation_id == E.correlation_id, outro.id != E.id, not_(outro.action.like("api.%"))))))
    return condicoes


class SqlAlchemyAuditoria:
    def __init__(self, db: Session) -> None:
        self.db = db

    def eventos(self, f: Filtros, *, antes: datetime | None, limite: int) -> list[dict[str, Any]]:
        consulta = select(E).where(*_onde(f))
        if antes:
            consulta = consulta.where(E.occurred_at < antes)
        linhas = self.db.scalars(consulta.order_by(E.occurred_at.desc(), E.id.desc()).limit(limite)).all()
        nomes = self.nomes({l.actor_id for l in linhas if l.actor_type == "user" and l.actor_id})
        return [_publico(l, nomes) for l in linhas]

    def grupos(self, f: Filtros, por: str, limite: int = 60) -> list[dict[str, Any]]:
        if por == "dia":
            chave = func.to_char(func.timezone(FUSO, E.occurred_at), "YYYY-MM-DD")
        elif por == "usuario":
            chave = func.coalesce(E.actor_id, literal("-"))
        else:
            chave = E.action
        ultimo = func.max(E.occurred_at)
        linhas = self.db.execute(
            select(chave.label("chave"), func.count().label("total"), ultimo.label("ultimo"), func.min(E.actor_type))
            .where(*_onde(f)).group_by(chave)
            .order_by(chave.desc() if por == "dia" else func.count().desc()).limit(limite)).all()
        nomes = self.nomes({c for c, *_ in linhas}) if por == "usuario" else {}
        return [{"chave": c, "total": total, "ultimo": u.isoformat() if u else None,
                 **({"nome": nomes.get(c, {}).get("nome"), "email": nomes.get(c, {}).get("email"), "tipo_de_ator": t} if por == "usuario" else {})}
                for c, total, u, t in linhas]

    def pessoas(self) -> list[dict[str, Any]]:
        ids = {i for (i,) in self.db.execute(select(E.actor_id).where(E.actor_type == "user", E.actor_id.is_not(None)).distinct())}
        nomes = self.nomes(ids)
        por_pessoa: dict[str, dict[str, Any]] = {}
        for i in sorted(ids, key=lambda x: (not str(x).isdigit(), str(x))):  # o número antes do e-mail antigo
            n = nomes.get(i, {})
            chave = n.get("email") or i
            if chave not in por_pessoa:
                por_pessoa[chave] = {"id": i, "nome": n.get("nome") or f"Usuário {i}", "email": n.get("email")}
        return sorted(por_pessoa.values(), key=lambda p: p["nome"].lower())

    def email_de(self, usuario: str) -> str | None:
        return self.nomes({usuario}).get(usuario, {}).get("email") if usuario.isdigit() else None

    def nomes(self, ids: set[str]) -> dict[str, dict[str, str | None]]:
        """Nome e e-mail de quem fez (só leitura do cadastro de pessoas)."""
        from modules.access.infrastructure.orm.models import AccessUserRecord

        numeros = [int(i) for i in ids if i and str(i).isdigit()]
        emails = [i for i in ids if i and "@" in str(i)]  # logins antigos guardavam o e-mail
        if not numeros and not emails:
            return {}
        saida: dict[str, dict[str, str | None]] = {}
        for u in self.db.scalars(select(AccessUserRecord).where(or_(AccessUserRecord.id.in_(numeros), AccessUserRecord.email.in_(emails)))):
            pessoa = {"nome": u.name, "email": u.email}
            saida[str(u.id)] = pessoa
            saida[u.email] = pessoa
        return saida


def _publico(l: E, nomes: dict[str, dict[str, str | None]]) -> dict[str, Any]:
    pessoa = nomes.get(l.actor_id or "", {})
    return {"id": l.id, "quando": l.occurred_at.isoformat() if l.occurred_at else None, "acao": l.action,
            "tipo": tipo_do_evento(l.action, l.actor_type), "tipo_de_ator": l.actor_type, "ator_id": l.actor_id,
            "ator_nome": pessoa.get("nome"), "ator_email": pessoa.get("email"),
            "recurso_tipo": l.resource_type, "recurso_id": l.resource_id, "antes": l.before, "depois": l.after,
            "detalhes": l.metadata_json or {}, "correlacao": l.correlation_id, "ip": l.ip, "navegador": l.user_agent}
