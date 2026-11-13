"""Webhooks e as chamadas recebidas (13/11/2026). Só o Orchestration escreve aqui."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import case, func, select, text
from sqlalchemy.orm import Session

from modules.orchestration.infrastructure.orm.models import WebhookChamadaRecord, WebhookRecord


class SqlAlchemyWebhooks:
    def __init__(self, db: Session) -> None:
        self.db = db

    def webhook(self, webhook_id: str) -> WebhookRecord | None:
        return self.db.get(WebhookRecord, webhook_id)

    def todos(self, automation_id: int | None = None) -> list[WebhookRecord]:
        consulta = select(WebhookRecord).order_by(WebhookRecord.nome)
        if automation_id is not None:
            consulta = consulta.where(WebhookRecord.automation_id == automation_id)
        return list(self.db.scalars(consulta).all())

    def nome_da_automacao(self, automation_id: int) -> str | None:
        return self.db.execute(text("SELECT name FROM automations WHERE id = :a"), {"a": automation_id}).scalar()

    def criar(self, *, id: str, automation_id: int, nome: str, descricao: str | None, token_hash: str, token_final: str,
              ips: list[str], limite: int, criado_por: str | None, agora: datetime) -> WebhookRecord:
        webhook = WebhookRecord(id=id, automation_id=automation_id, nome=nome, descricao=descricao, ativo=True,
                                token_hash=token_hash, token_final=token_final, token_criado_em=agora, ips_permitidos=ips,
                                limite_por_minuto=limite, criado_por=criado_por, criado_em=agora, atualizado_em=agora)
        self.db.add(webhook)
        self.db.flush()
        return webhook

    def mudar(self, webhook: WebhookRecord, dados: dict[str, Any], agora: datetime) -> None:
        for campo, valor in dados.items():
            setattr(webhook, campo, valor)
        webhook.atualizado_em = agora
        self.db.flush()

    def trocar_token(self, webhook: WebhookRecord, token_hash: str, final: str, agora: datetime) -> None:
        webhook.token_hash = token_hash
        webhook.token_final = final
        webhook.token_criado_em = agora
        webhook.atualizado_em = agora
        self.db.flush()

    def marcar_uso(self, webhook: WebhookRecord, agora: datetime) -> None:
        webhook.ultimo_uso_em = agora
        self.db.flush()

    def apagar(self, webhook: WebhookRecord) -> None:
        self.db.delete(webhook)
        self.db.flush()

    # -- chamadas -------------------------------------------------------------------------------
    def registrar(self, **dados: Any) -> None:
        self.db.add(WebhookChamadaRecord(**dados))
        self.db.flush()

    def chamadas(self, webhook_id: str, limite: int) -> list[WebhookChamadaRecord]:
        return list(self.db.scalars(select(WebhookChamadaRecord).where(WebhookChamadaRecord.webhook_id == webhook_id)
                                    .order_by(WebhookChamadaRecord.recebida_em.desc()).limit(max(1, min(limite, 200)))).all())

    def chamadas_desde(self, webhook_id: str, desde: datetime) -> int:
        return int(self.db.scalar(select(func.count()).select_from(WebhookChamadaRecord).where(
            WebhookChamadaRecord.webhook_id == webhook_id, WebhookChamadaRecord.recebida_em >= desde)) or 0)

    def aceita_com_chave(self, webhook_id: str, chave: str, desde: datetime) -> WebhookChamadaRecord | None:
        return self.db.scalar(select(WebhookChamadaRecord).where(
            WebhookChamadaRecord.webhook_id == webhook_id, WebhookChamadaRecord.chave_idempotencia == chave,
            WebhookChamadaRecord.situacao == "aceita", WebhookChamadaRecord.recebida_em >= desde)
            .order_by(WebhookChamadaRecord.recebida_em.desc()).limit(1))

    def contagem(self, webhook_id: str, desde: datetime) -> tuple[int, int]:
        aceitas, recusadas = self.db.execute(select(
            func.count(case((WebhookChamadaRecord.situacao.in_(("aceita", "repetida")), 1))),
            func.count(case((WebhookChamadaRecord.situacao == "recusada", 1))),
        ).where(WebhookChamadaRecord.webhook_id == webhook_id, WebhookChamadaRecord.recebida_em >= desde)).one()
        return int(aceitas or 0), int(recusadas or 0)
