"""Notificações (Fase 6): preferências, ocorrências, avisos por endereço e a leitura do que aconteceu."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from modules.telemetry.domain.notificacoes import FILA_MINUTOS_PADRAO, Ocorrencia, Pessoa
from modules.telemetry.infrastructure.orm.models import (
    ExecutionEventRecord,
    NotificationDeliveryRecord,
    NotificationPreferenceRecord,
    NotificationRecord,
)

GESTORES = ("admin", "manager")
FINAIS = ("succeeded", "partially_succeeded", "failed", "cancelled", "timed_out")


class SqlAlchemyNotificacoes:
    def __init__(self, db: Session) -> None:
        self.db = db

    # --- preferências -------------------------------------------------------------------
    def preferencia(self, user_id: int) -> tuple[list[str], int]:
        linha = self.db.get(NotificationPreferenceRecord, user_id)
        return (list(linha.tipos or []), linha.fila_minutos) if linha else ([], FILA_MINUTOS_PADRAO)

    def gravar_preferencia(self, user_id: int, tipos: list[str], fila_minutos: int) -> None:
        linha = self.db.get(NotificationPreferenceRecord, user_id)
        if linha is None:
            linha = NotificationPreferenceRecord(user_id=user_id)
            self.db.add(linha)
        linha.tipos = sorted(tipos)
        linha.fila_minutos = fila_minutos
        self.db.flush()

    def pessoas(self) -> list[tuple[Pessoa, Any]]:
        """Quem ligou ao menos um tipo e está ativo, com o registro do usuário (para a permissão)."""
        from modules.access.infrastructure.orm.models import AccessUserRecord

        linhas = self.db.execute(
            select(NotificationPreferenceRecord, AccessUserRecord)
            .join(AccessUserRecord, AccessUserRecord.id == NotificationPreferenceRecord.user_id)
            .where(AccessUserRecord.is_active.is_(True), AccessUserRecord.status == "active")
            .order_by(AccessUserRecord.id)
        ).all()
        saida = []
        for pref, usuario in linhas:
            if not pref.tipos:
                continue
            slug = getattr(getattr(usuario, "role", None), "slug", None)
            saida.append((Pessoa(usuario.id, usuario.email, slug in GESTORES, frozenset(pref.tipos), pref.fila_minutos), usuario))
        return saida

    # --- ocorrências e avisos ------------------------------------------------------------
    def registradas(self, chaves: list[str]) -> set[str]:
        if not chaves:
            return set()
        return set(self.db.scalars(select(NotificationRecord.chave).where(NotificationRecord.chave.in_(chaves))))

    def registrar(self, ocorrencia: Ocorrencia, destinatarios: list[tuple[int, str]]) -> bool:
        """Grava a ocorrência e um aviso por endereço. Se a chave já existe, não faz nada."""
        novo_id = f"ntf_{uuid4().hex}"
        criado = self.db.execute(insert(NotificationRecord).values(
            id=novo_id, chave=ocorrencia.chave, tipos=sorted(ocorrencia.tipos), titulo=ocorrencia.titulo[:300],
            texto=ocorrencia.texto, link=ocorrencia.link, automation_id=ocorrencia.automation_id,
            execution_id=ocorrencia.execution_id, quando=ocorrencia.quando,
        ).on_conflict_do_nothing(index_elements=["chave"]).returning(NotificationRecord.id)).scalar()
        if criado is None:
            return False
        for user_id, email in destinatarios:
            self.db.execute(insert(NotificationDeliveryRecord).values(
                id=f"ntd_{uuid4().hex}", notification_id=criado, user_id=user_id, email=email,
            ).on_conflict_do_nothing(index_elements=["notification_id", "email"]))
        self.db.flush()
        return True

    def do_usuario(self, user_id: int, limite: int) -> tuple[list[dict[str, Any]], int]:
        linhas = self.db.execute(
            select(NotificationDeliveryRecord, NotificationRecord)
            .join(NotificationRecord, NotificationRecord.id == NotificationDeliveryRecord.notification_id)
            .where(NotificationDeliveryRecord.user_id == user_id)
            .order_by(NotificationRecord.quando.desc()).limit(limite)
        ).all()
        nao_lidas = self.db.scalar(select(func.count()).select_from(NotificationDeliveryRecord).where(
            NotificationDeliveryRecord.user_id == user_id, NotificationDeliveryRecord.lida_em.is_(None))) or 0
        return [{
            "id": d.id, "tipos": list(n.tipos or []), "titulo": n.titulo, "texto": n.texto, "link": n.link,
            "quando": n.quando.isoformat(), "lida": d.lida_em is not None, "email": d.email_status,
        } for d, n in linhas], int(nao_lidas)

    def marcar_lidas(self, user_id: int, ids: list[str] | None, agora: datetime) -> int:
        filtro = [NotificationDeliveryRecord.user_id == user_id, NotificationDeliveryRecord.lida_em.is_(None)]
        if ids is not None:
            filtro.append(NotificationDeliveryRecord.id.in_(ids))
        r = self.db.execute(update(NotificationDeliveryRecord).where(*filtro).values(lida_em=agora))
        self.db.flush()
        return int(r.rowcount or 0)

    # --- envio por e-mail ----------------------------------------------------------------
    def pendentes(self, limite: int) -> list[tuple[NotificationDeliveryRecord, NotificationRecord]]:
        return list(self.db.execute(
            select(NotificationDeliveryRecord, NotificationRecord)
            .join(NotificationRecord, NotificationRecord.id == NotificationDeliveryRecord.notification_id)
            .where(NotificationDeliveryRecord.email_status == "pendente")
            .order_by(NotificationDeliveryRecord.created_at).limit(limite).with_for_update(skip_locked=True,
                                                                                          of=NotificationDeliveryRecord)
        ).all())


class SqlAlchemyLeituraDeOcorrencias:
    """O que aconteceu desde ``desde``: execuções que terminaram, atenções, máquinas e fila."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def _automacao_das_execucoes(self, ids: list[str]) -> dict[str, tuple[int, str]]:
        from modules.catalog.infrastructure.orm.models import CatalogAutomationRecord, CatalogAutomationVersionRecord
        from modules.orchestration.infrastructure.orm.models import TaskExecutionRecord

        if not ids:
            return {}
        linhas = self.db.execute(
            select(TaskExecutionRecord.execution_id, CatalogAutomationRecord.id, CatalogAutomationRecord.name)
            .join(CatalogAutomationVersionRecord, CatalogAutomationVersionRecord.id == TaskExecutionRecord.automation_version_id)
            .join(CatalogAutomationRecord, CatalogAutomationRecord.id == CatalogAutomationVersionRecord.automation_id)
            .where(TaskExecutionRecord.execution_id.in_(ids))
        ).all()
        return {e: (a, n) for e, a, n in linhas}

    def terminadas(self, desde: datetime) -> list[dict[str, Any]]:
        from modules.orchestration.infrastructure.orm.models import OrchestrationExecutionRecord

        execucoes = list(self.db.scalars(
            select(OrchestrationExecutionRecord)
            .where(OrchestrationExecutionRecord.status.in_(FINAIS), OrchestrationExecutionRecord.completed_at >= desde)
            .order_by(OrchestrationExecutionRecord.completed_at)
        ))
        nomes = self._automacao_das_execucoes([e.id for e in execucoes])
        return [{"execution_id": e.id, "situacao": e.status, "quando": e.completed_at, "falha": e.failure_summary,
                 "automation_id": nomes.get(e.id, (None, None))[0], "automacao": nomes.get(e.id, (None, None))[1]}
                for e in execucoes]

    def comunicacao(self, agora: datetime) -> list[dict[str, Any]]:
        """Execuções diretas rodando sem comunicação há 30 s, ou com cancelamento sem resposta há 2 min."""
        from modules.dispatch.domain.comunicacao import AVISO_SEM_COMUNICACAO, PRAZO_DO_CANCELAMENTO
        from modules.dispatch.infrastructure.repositories.sqlalchemy_job_tokens import SqlAlchemyDirectCommandStore
        from modules.telemetry.infrastructure.repositories.sqlalchemy_painel import SqlAlchemyPainelReader

        rodando = [r for r in SqlAlchemyPainelReader(self.db).rodando() if r["modo"] == "direct"]
        paradas = SqlAlchemyDirectCommandStore(self.db).paradas_pedidas([r["tentativa_id"] for r in rodando])
        saida = []
        for r in rodando:
            base = {"execution_id": r["execucao_id"], "attempt_id": r["tentativa_id"], "automation_id": r["automation_id"],
                    "automacao": r["automacao"]}
            parada = paradas.get(r["tentativa_id"])
            if parada and parada["tipo"] == "cancelar" and agora - parada["pedido_em"] >= PRAZO_DO_CANCELAMENTO:
                saida.append({**base, "tipo": "cancelamento_sem_resposta", "recebido": bool(parada["recebido_em"]),
                              "desde": parada["pedido_em"]})
            elif r["sinal_da_instancia"] is not None and agora - r["sinal_da_instancia"] >= AVISO_SEM_COMUNICACAO:
                saida.append({**base, "tipo": "sem_comunicacao", "desde": r["sinal_da_instancia"]})
        return saida

    def atencoes(self, desde: datetime) -> list[dict[str, Any]]:
        linhas = self.db.execute(
            select(ExecutionEventRecord.execution_id, ExecutionEventRecord.payload, ExecutionEventRecord.occurred_at)
            .where(ExecutionEventRecord.event_type == "automation.event",
                   ExecutionEventRecord.payload["type"].astext == "atencao",
                   ExecutionEventRecord.received_at >= desde)
            .order_by(ExecutionEventRecord.received_at)
        ).all()
        nomes = self._automacao_das_execucoes(list({e for e, _, _ in linhas}))
        saida = []
        for execucao, payload, quando in linhas:
            corpo = (payload or {}).get("payload") or {}
            saida.append({"execution_id": execucao, "item": corpo.get("item"), "motivo": corpo.get("motivo"),
                          "quando": quando, "automation_id": nomes.get(execucao, (None, None))[0],
                          "automacao": nomes.get(execucao, (None, None))[1]})
        return saida

    def ultimos_sinais(self) -> dict[str, datetime]:
        """Último sinal de cada máquina: o mais recente entre os agentes e as instâncias diretas dela."""
        from modules.fleet.infrastructure.orm.models import AgentRecord, DirectInstanceRecord

        sinais: dict[str, datetime] = {}
        for maquina, quando in [
            *self.db.execute(select(AgentRecord.machine_id, func.max(AgentRecord.last_seen_at))
                             .where(AgentRecord.machine_id.is_not(None)).group_by(AgentRecord.machine_id)).all(),
            *self.db.execute(select(DirectInstanceRecord.machine_id, func.max(DirectInstanceRecord.last_seen_at))
                             .where(DirectInstanceRecord.machine_id.is_not(None)).group_by(DirectInstanceRecord.machine_id)).all(),
        ]:
            if quando is not None and (maquina not in sinais or quando > sinais[maquina]):
                sinais[maquina] = quando
        return sinais

    def ultimo_inicio(self) -> datetime | None:
        from modules.orchestration.infrastructure.orm.models import ExecutionAttemptRecord

        return self.db.scalar(select(func.max(ExecutionAttemptRecord.started_at)))
