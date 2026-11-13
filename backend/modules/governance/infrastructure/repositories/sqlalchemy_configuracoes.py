"""O que foi mudado nas configurações do sistema: limites (``system_limits``, escopo global) e
prazos de limpeza (``regras_de_limpeza``). Sem linha, vale o padrão do catálogo."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.governance.application.configuracoes import PrazoGravado
from modules.governance.domain.configuracoes import Limite
from modules.governance.infrastructure.orm.models import RegraDeLimpezaRecord, SystemLimitRecord

UNIDADE_NA_TABELA = {"mb": "mb", "segundos": "seconds", "quantidade": "count", "bytes": "bytes"}


class SqlAlchemyConfiguracoes:
    def __init__(self, db: Session) -> None:
        self.db = db

    # limites
    def limites(self) -> dict[str, tuple[int, datetime | None]]:
        linhas = self.db.scalars(select(SystemLimitRecord).where(SystemLimitRecord.organization_id.is_(None))
                                 .order_by(SystemLimitRecord.id.desc()))
        return {linha.key: (int(linha.value), linha.updated_at) for linha in linhas}  # a mais antiga vence, como em ler_limite

    def gravar_limite(self, item: Limite, valor: int) -> None:
        linha = self.db.scalar(select(SystemLimitRecord).where(
            SystemLimitRecord.key == item.chave, SystemLimitRecord.organization_id.is_(None)).order_by(SystemLimitRecord.id).limit(1))
        if linha is None:
            linha = SystemLimitRecord(key=item.chave, organization_id=None, metadata_json={})
            self.db.add(linha)
        linha.value = valor
        linha.unit = UNIDADE_NA_TABELA.get(item.unidade, item.unidade)
        linha.description = item.descricao
        self.db.flush()

    # limpeza
    def prazos(self) -> dict[str, PrazoGravado]:
        return {linha.chave: PrazoGravado(linha.personalizado, linha.dias, linha.atualizado_por, linha.atualizado_em,
                                          linha.ultima_limpeza_em, linha.ultima_limpeza_apagados, linha.total_apagados or 0)
                for linha in self.db.scalars(select(RegraDeLimpezaRecord))}

    def _linha(self, chave: str) -> RegraDeLimpezaRecord:
        linha = self.db.get(RegraDeLimpezaRecord, chave)
        if linha is None:
            linha = RegraDeLimpezaRecord(chave=chave, personalizado=False, total_apagados=0)
            self.db.add(linha)
        return linha

    def gravar_prazo(self, chave: str, dias: int | None, personalizado: bool, por: str | None, agora: datetime) -> None:
        linha = self._linha(chave)
        linha.dias = dias
        linha.personalizado = personalizado
        linha.atualizado_por = por
        linha.atualizado_em = agora
        self.db.flush()

    def registrar_passada(self, chave: str, apagados: int, agora: datetime) -> None:
        linha = self._linha(chave)
        linha.ultima_limpeza_em = agora
        linha.ultima_limpeza_apagados = apagados
        linha.total_apagados = (linha.total_apagados or 0) + apagados
        self.db.flush()
