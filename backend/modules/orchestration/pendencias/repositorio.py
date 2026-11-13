"""Pendências (13/11/2026): leitura dos itens em atenção e gravação das pendências e avisos."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from modules.orchestration.pendencias.modelos import PendenciaAvisoRecord, PendenciaRecord

TERMINAIS = ("succeeded", "failed", "cancelled", "timed_out", "lost", "completed", "partial")


class SqlAlchemyPendencias:
    def __init__(self, db: Session) -> None:
        self.db = db

    # -- abrir ------------------------------------------------------------------------------------
    def sincronizar(self, desde: datetime) -> int:
        """Cada item que terminou em atenção vira uma pendência (uma vez só); completa rótulo e motivo."""
        novos = self.db.execute(text(
            "INSERT INTO pendencias (id, execution_id, automation_id, item_key, rotulo, motivo, situacao, criada_em) "
            "SELECT 'pnd_' || substr(md5(random()::text || i.id), 1, 24), i.execution_id, i.automation_id, i.item_key, i.label, "
            "       i.attention->>'motivo', 'aguardando', coalesce(i.completed_at, now()) "
            "FROM execution_items i WHERE i.status = 'atencao' AND coalesce(i.completed_at, i.updated_at) >= :desde "
            "ON CONFLICT (execution_id, item_key) DO NOTHING"), {"desde": desde}).rowcount
        self.db.execute(text(
            "UPDATE pendencias p SET rotulo = coalesce(p.rotulo, i.label), motivo = coalesce(p.motivo, i.attention->>'motivo') "
            "FROM execution_items i WHERE i.execution_id = p.execution_id AND i.item_key = p.item_key "
            "AND i.status = 'atencao' AND ((p.rotulo IS NULL AND i.label IS NOT NULL) "
            "OR (p.motivo IS NULL AND i.attention->>'motivo' IS NOT NULL))"))  # só quando há o que preencher
        return int(novos or 0)

    def garantir(self, execution_id: str, automation_id: int, item_keys: list[str], agora: datetime) -> list[PendenciaRecord]:
        """Pendências para os itens que a automação marcou no e-mail (o evento de atenção pode chegar depois)."""
        for chave in item_keys:
            self.db.execute(text(
                "INSERT INTO pendencias (id, execution_id, automation_id, item_key, rotulo, motivo, situacao, criada_em) "
                "SELECT :id, :e, :a, :k, i.label, i.attention->>'motivo', 'aguardando', :agora FROM (SELECT 1) x "
                "LEFT JOIN execution_items i ON i.execution_id = :e AND i.item_key = :k "
                "ON CONFLICT (execution_id, item_key) DO NOTHING"),
                {"id": f"pnd_{uuid4().hex[:24]}", "e": execution_id, "a": automation_id, "k": chave, "agora": agora})
        self.db.flush()
        return self.da_execucao(execution_id, item_keys)

    # -- ler --------------------------------------------------------------------------------------
    def da_execucao(self, execution_id: str, item_keys: list[str] | None = None, travar: bool = False) -> list[PendenciaRecord]:
        consulta = select(PendenciaRecord).where(PendenciaRecord.execution_id == execution_id)
        if item_keys is not None:
            consulta = consulta.where(PendenciaRecord.item_key.in_(item_keys))
        if travar:
            consulta = consulta.with_for_update()
        return list(self.db.scalars(consulta.order_by(PendenciaRecord.item_key)))

    def aguardando(self, limite: int = 500) -> list[PendenciaRecord]:
        return list(self.db.scalars(select(PendenciaRecord).where(PendenciaRecord.situacao == "aguardando")
                                    .order_by(PendenciaRecord.criada_em.desc()).limit(limite)))

    def aviso(self, aviso_id: str) -> PendenciaAvisoRecord | None:
        return self.db.get(PendenciaAvisoRecord, aviso_id)

    def avisos_da_execucao(self, execution_id: str) -> list[PendenciaAvisoRecord]:
        return list(self.db.scalars(select(PendenciaAvisoRecord).where(PendenciaAvisoRecord.execution_id == execution_id)))

    def execucao(self, execution_id: str) -> dict[str, Any] | None:
        linha = self.db.execute(text(
            "SELECT e.id, e.status, e.requested_by, e.input, e.created_at, "
            "(SELECT v.automation_id FROM task_executions t JOIN automation_versions v ON v.id = t.automation_version_id "
            " WHERE t.execution_id = e.id LIMIT 1) AS automation_id "
            "FROM orchestration_executions e WHERE e.id = :e"), {"e": execution_id}).mappings().first()
        return dict(linha) if linha else None

    def itens_do_pedido(self, execution_id: str) -> dict[str, dict[str, Any]]:
        """O retrato de cada item no pedido original (rótulo, grupo, atributos, configuração)."""
        saida: dict[str, dict[str, Any]] = {}
        for (entrada,) in self.db.execute(text("SELECT input FROM task_executions WHERE execution_id = :e"), {"e": execution_id}):
            for item in (entrada or {}).get("dados_dos_itens") or []:
                if isinstance(item, dict) and item.get("chave") is not None:
                    saida[str(item["chave"])] = item
        return saida

    def execucoes_para_avisar(self, desde: datetime) -> list[str]:
        """Execuções que terminaram com pendências aguardando e sem nenhum aviso (o Portal avisa quem pediu)."""
        return [e for (e,) in self.db.execute(text(
            "SELECT DISTINCT p.execution_id FROM pendencias p JOIN orchestration_executions e ON e.id = p.execution_id "
            "WHERE p.situacao = 'aguardando' AND p.criada_em >= :desde AND e.status = ANY(:terminais) "
            "AND NOT EXISTS (SELECT 1 FROM pendencia_avisos a WHERE a.execution_id = p.execution_id)"),
            {"desde": desde, "terminais": list(TERMINAIS)})]

    def nome_da_automacao(self, automation_id: int) -> str | None:
        return self.db.execute(text("SELECT name FROM automations WHERE id = :a"), {"a": automation_id}).scalar()

    def usuario(self, user_id: str | None) -> dict[str, Any] | None:
        if not user_id or not str(user_id).isdigit():
            return None
        linha = self.db.execute(text("SELECT id, name, email, is_active FROM users WHERE id = :u"), {"u": int(user_id)}).mappings().first()
        return dict(linha) if linha else None

    # -- gravar -----------------------------------------------------------------------------------
    def criar_aviso(self, *, execution_id: str, automation_id: int, item_keys: list[str], destinatarios: list[str],
                    origem: str, agora: datetime) -> PendenciaAvisoRecord:
        aviso = PendenciaAvisoRecord(id=f"pav_{uuid4().hex[:24]}", execution_id=execution_id, automation_id=automation_id,
                                     item_keys=item_keys, destinatarios=destinatarios, origem=origem, criado_em=agora)
        self.db.add(aviso)
        self.db.flush()
        return aviso

    def ligar_email(self, aviso: PendenciaAvisoRecord, email_id: str) -> None:
        aviso.email_id = email_id
        self.db.flush()

    def resolver(self, pendencias: list[PendenciaRecord], *, situacao: str, por: str | None, via: str, agora: datetime,
                 continuacao: str | None = None) -> None:
        for p in pendencias:
            p.situacao = situacao
            p.resolvida_em = agora
            p.resolvida_por = por
            p.resolvida_via = via
            p.continuacao_execution_id = continuacao
        self.db.flush()

    def ligar_continuacao(self, pendencias: list[PendenciaRecord], execution_id: str) -> None:
        for p in pendencias:
            p.continuacao_execution_id = execution_id
        self.db.flush()

    def substituir(self, automation_id: int, item_keys: list[str], nova_execucao: str, por: str | None, agora: datetime) -> int:
        """O item rodou de novo por outro caminho (Executar, webhook): a pendência fecha."""
        if not item_keys:
            return 0
        r = self.db.execute(update(PendenciaRecord).where(
            PendenciaRecord.automation_id == automation_id, PendenciaRecord.item_key.in_(item_keys),
            PendenciaRecord.situacao == "aguardando", PendenciaRecord.execution_id != nova_execucao,
        ).values(situacao="substituida", resolvida_em=agora, resolvida_por=por, resolvida_via="outra_execucao",
                 continuacao_execution_id=nova_execucao))
        self.db.flush()
        return int(r.rowcount or 0)
