"""Tokens de acesso (13/11/2026): desafio, código, navegador confiável, redefinir e convite."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from modules.access.infrastructure.orm.models import AccessUserRecord, AcessoTokenRecord, ServiceAccountRecord


class SqlAlchemyAcesso:
    def __init__(self, db: Session) -> None:
        self.db = db

    # -- pessoas ----------------------------------------------------------------------------------
    def usuario_por_email(self, email: str) -> AccessUserRecord | None:
        return self.db.scalar(select(AccessUserRecord).where(func.lower(AccessUserRecord.email) == email.strip().lower()))

    def usuario(self, user_id: int) -> AccessUserRecord | None:
        return self.db.get(AccessUserRecord, user_id)

    def e_tecnico(self, user_id: int) -> bool:
        return self.db.scalar(select(ServiceAccountRecord.id).where(ServiceAccountRecord.user_id == user_id)) is not None

    def salvar(self) -> None:
        self.db.flush()

    # -- tokens -----------------------------------------------------------------------------------
    def criar(self, *, user_id: int, tipo: str, hash: str, expira_em: datetime, agora: datetime, dados: dict[str, Any] | None = None,
              ip: str | None = None) -> AcessoTokenRecord:
        token = AcessoTokenRecord(id=f"atk_{uuid4().hex[:24]}", user_id=user_id, tipo=tipo, hash=hash, criado_em=agora,
                                  expira_em=expira_em, tentativas=0, dados=dados or {}, ip=ip)
        self.db.add(token)
        self.db.flush()
        return token

    def por_hash(self, tipo: str, hash: str, travar: bool = False) -> AcessoTokenRecord | None:
        consulta = select(AcessoTokenRecord).where(AcessoTokenRecord.tipo == tipo, AcessoTokenRecord.hash == hash)
        return self.db.scalar(consulta.with_for_update() if travar else consulta)

    def codigo_do_desafio(self, desafio_id: str) -> AcessoTokenRecord | None:
        return self.db.scalar(select(AcessoTokenRecord).where(
            AcessoTokenRecord.tipo == "codigo", AcessoTokenRecord.usado_em.is_(None),
            AcessoTokenRecord.dados["desafio"].astext == desafio_id).order_by(AcessoTokenRecord.criado_em.desc()).limit(1).with_for_update())

    def codigos_do_desafio_desde(self, desafio_id: str, desde: datetime) -> int:
        return int(self.db.scalar(select(func.count()).select_from(AcessoTokenRecord).where(
            AcessoTokenRecord.tipo == "codigo", AcessoTokenRecord.dados["desafio"].astext == desafio_id,
            AcessoTokenRecord.criado_em >= desde)) or 0)

    def criados_desde(self, user_id: int, tipos: tuple[str, ...], desde: datetime) -> int:
        return int(self.db.scalar(select(func.count()).select_from(AcessoTokenRecord).where(
            AcessoTokenRecord.user_id == user_id, AcessoTokenRecord.tipo.in_(tipos), AcessoTokenRecord.criado_em >= desde)) or 0)

    def usar(self, token: AcessoTokenRecord, agora: datetime) -> None:
        token.usado_em = agora
        self.db.flush()

    def invalidar(self, user_id: int, tipos: tuple[str, ...], agora: datetime, exceto: str | None = None) -> int:
        consulta = update(AcessoTokenRecord).where(AcessoTokenRecord.user_id == user_id, AcessoTokenRecord.tipo.in_(tipos),
                                                   AcessoTokenRecord.usado_em.is_(None))
        if exceto:
            consulta = consulta.where(AcessoTokenRecord.id != exceto)
        r = self.db.execute(consulta.values(usado_em=agora))
        self.db.flush()
        return int(r.rowcount or 0)

    def dispositivos(self, user_id: int, agora: datetime) -> list[AcessoTokenRecord]:
        return list(self.db.scalars(select(AcessoTokenRecord).where(
            AcessoTokenRecord.user_id == user_id, AcessoTokenRecord.tipo == "dispositivo", AcessoTokenRecord.usado_em.is_(None),
            AcessoTokenRecord.expira_em > agora).order_by(AcessoTokenRecord.criado_em.desc())))

    def apagar_vencidos(self, antes: datetime) -> int:
        r = self.db.execute(delete(AcessoTokenRecord).where(AcessoTokenRecord.expira_em < antes))
        self.db.flush()
        return int(r.rowcount or 0)
