"""Histórico de etapas (step_runs), pausas e estimativas congeladas: dono é o Telemetry."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from modules.catalog.infrastructure.orm.models import AutomationManifestRecord, CatalogAutomationVersionRecord
from modules.telemetry.domain.estimativas import EtapaDeclarada, Medicao
from modules.telemetry.infrastructure.orm.models import AttemptPauseRecord, EstimateSnapshotRecord, StepRunRecord


@dataclass(frozen=True)
class VersionManifest:
    automation_id: int
    steps: tuple[EtapaDeclarada, ...]
    work_attributes: tuple[str, ...] | None  # None: o manifesto não declara itens


class SqlAlchemyManifestReader:
    """Leitura do manifesto normalizado da versão (Catalog), só para consulta."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self._cache: dict[int, VersionManifest | None] = {}

    def get(self, automation_version_id: int) -> VersionManifest | None:
        if automation_version_id in self._cache:
            return self._cache[automation_version_id]
        version = self.db.get(CatalogAutomationVersionRecord, automation_version_id)
        if version is None:
            self._cache[automation_version_id] = None
            return None
        manifest: dict[str, Any] = {}
        if getattr(version, "manifest_id", None):
            row = self.db.get(AutomationManifestRecord, version.manifest_id)
            manifest = dict(row.normalized_content or {}) if row else {}
        if not manifest:
            manifest = dict(getattr(version, "manifest", None) or {})
        steps = tuple(
            EtapaDeclarada(s["key"], s.get("name") or s["key"], bool(s.get("per_item", True)), bool(s.get("per_task", False)))
            for s in manifest.get("steps") or [] if isinstance(s, dict) and s.get("key")
        )
        items = manifest.get("items") if isinstance(manifest.get("items"), dict) else None
        work = tuple(items.get("work_attributes") or ()) if items else None
        result = VersionManifest(int(version.automation_id), steps, work)
        self._cache[automation_version_id] = result
        return result


class SqlAlchemyStepRunStore:
    def __init__(self, db: Session) -> None:
        self.db = db

    # -- etapas -------------------------------------------------------------------------
    def open(self, *, run_id: str, execution_id: str, task_execution_id: str, execution_attempt_id: str,
             automation_id: int, automation_version_id: int, step_key: str, item_key: str | None,
             work_signature: str, planned_tasks: int | None, started_at: datetime, machine_id: str | None,
             executor_type: str, start_sequence: int) -> None:
        self.db.execute(
            insert(StepRunRecord).values(
                id=run_id, execution_id=execution_id, task_execution_id=task_execution_id,
                execution_attempt_id=execution_attempt_id, automation_id=automation_id,
                automation_version_id=automation_version_id, step_key=step_key, item_key=item_key,
                work_signature=work_signature, status="executando", planned_tasks=planned_tasks, tasks=0,
                started_at=started_at, paused_seconds=0, machine_id=machine_id, executor_type=executor_type,
                start_sequence=start_sequence,
            ).on_conflict_do_nothing(index_elements=["execution_attempt_id", "start_sequence"])
        )

    def open_run(self, execution_attempt_id: str, step_key: str, item_key: str | None) -> StepRunRecord | None:
        filtro = StepRunRecord.item_key.is_(None) if item_key is None else StepRunRecord.item_key == item_key
        return self.db.scalar(
            select(StepRunRecord)
            .where(StepRunRecord.execution_attempt_id == execution_attempt_id, StepRunRecord.step_key == step_key,
                   filtro, StepRunRecord.status == "executando")
            .order_by(StepRunRecord.start_sequence.desc()).limit(1)
        )

    def close(self, run: StepRunRecord, *, status: str, tasks: int, completed_at: datetime,
              gross: float, paused: float, net: float) -> None:
        run.status, run.tasks, run.completed_at = status, tasks, completed_at
        run.gross_seconds, run.paused_seconds, run.net_seconds = gross, paused, net
        self.db.add(run)
        self.db.flush()

    def for_execution(self, execution_id: str) -> list[StepRunRecord]:
        return list(self.db.scalars(select(StepRunRecord).where(StepRunRecord.execution_id == execution_id)
                                    .order_by(StepRunRecord.started_at)))

    def history(self, automation_id: int, step_keys: Iterable[str]) -> list[Medicao]:
        """Todas as medições concluídas dessas etapas na automação; os filtros das regras ficam no domínio."""
        rows = self.db.scalars(
            select(StepRunRecord).where(StepRunRecord.automation_id == automation_id,
                                        StepRunRecord.step_key.in_(list(step_keys)),
                                        StepRunRecord.completed_at.is_not(None))
        )
        return [Medicao(r.execution_id, r.automation_id, r.step_key, r.item_key, r.work_signature, r.status,
                        r.tasks, float(r.net_seconds or 0), r.completed_at) for r in rows]

    # -- pausas -------------------------------------------------------------------------
    def pause_started(self, *, execution_attempt_id: str, start_sequence: int, reason: str, item_key: str | None,
                      at: datetime) -> None:
        self.db.execute(insert(AttemptPauseRecord).values(
            execution_attempt_id=execution_attempt_id, start_sequence=start_sequence, reason=reason,
            item_key=item_key, started_at=at,
        ).on_conflict_do_nothing(index_elements=["execution_attempt_id", "start_sequence"]))

    def pause_ended(self, *, execution_attempt_id: str, reason: str, at: datetime) -> None:
        aberta = self.db.scalar(
            select(AttemptPauseRecord.start_sequence)
            .where(AttemptPauseRecord.execution_attempt_id == execution_attempt_id, AttemptPauseRecord.reason == reason,
                   AttemptPauseRecord.ended_at.is_(None))
            .order_by(AttemptPauseRecord.start_sequence.desc()).limit(1)
        )
        if aberta is not None:
            self.db.execute(update(AttemptPauseRecord)
                            .where(AttemptPauseRecord.execution_attempt_id == execution_attempt_id,
                                   AttemptPauseRecord.start_sequence == aberta)
                            .values(ended_at=at))

    def pauses(self, execution_attempt_id: str) -> list[tuple[datetime, datetime | None]]:
        rows = self.db.execute(select(AttemptPauseRecord.started_at, AttemptPauseRecord.ended_at)
                               .where(AttemptPauseRecord.execution_attempt_id == execution_attempt_id)).all()
        return [(a, b) for a, b in rows]

    # -- estimativas congeladas -----------------------------------------------------------
    def snapshot(self, execution_attempt_id: str) -> dict[str, dict[str, Any]]:
        rows = self.db.scalars(select(EstimateSnapshotRecord)
                               .where(EstimateSnapshotRecord.execution_attempt_id == execution_attempt_id))
        return {r.entry_key: dict(r.payload) for r in rows}

    def freeze(self, *, execution_attempt_id: str, execution_id: str, task_execution_id: str, cutoff: datetime,
               entries: dict[str, dict[str, Any]]) -> None:
        """Uma vez gravada, a entrada não muda (regra 8)."""
        if not entries:
            return
        self.db.execute(insert(EstimateSnapshotRecord).values([
            {"execution_attempt_id": execution_attempt_id, "entry_key": key, "execution_id": execution_id,
             "task_execution_id": task_execution_id, "cutoff": cutoff, "payload": payload}
            for key, payload in entries.items()
        ]).on_conflict_do_nothing(index_elements=["execution_attempt_id", "entry_key"]))


class SqlAlchemyExecutionJobsReader:
    """Jobs de uma execução com a tentativa mais recente (leitura de Orchestration)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def jobs(self, execution_id: str) -> list[dict[str, Any]]:
        from modules.orchestration.infrastructure.orm.models import ExecutionAttemptRecord, TaskExecutionRecord

        tarefas = list(self.db.scalars(select(TaskExecutionRecord).where(TaskExecutionRecord.execution_id == execution_id)
                                       .order_by(TaskExecutionRecord.created_at)))
        saida = []
        for tarefa in tarefas:
            tentativa = self.db.scalar(select(ExecutionAttemptRecord)
                                       .where(ExecutionAttemptRecord.task_execution_id == tarefa.id)
                                       .order_by(ExecutionAttemptRecord.attempt_number.desc()).limit(1))
            saida.append({
                "job_id": tarefa.id,
                "automation_version_id": tarefa.automation_version_id,
                "status": tarefa.status,
                "tentativa_id": tentativa.id if tentativa else None,
                "tentativa_numero": tentativa.attempt_number if tentativa else None,
                "maquina_id": tentativa.machine_id if tentativa else None,
                "modo": tentativa.executor_type if tentativa else None,
            })
        return saida


def latest_manifest_for_automation(db: Session, automation_id: int) -> VersionManifest | None:
    """Etapas da versão mais recente da automação (para a tela de tempos)."""
    versao = db.scalar(select(CatalogAutomationVersionRecord.id)
                       .where(CatalogAutomationVersionRecord.automation_id == automation_id)
                       .order_by(CatalogAutomationVersionRecord.id.desc()).limit(1))
    return SqlAlchemyManifestReader(db).get(versao) if versao is not None else None
