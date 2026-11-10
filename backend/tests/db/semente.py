"""Dados mínimos pelas tabelas reais e roteiros de eventos no formato da Integração Contábil."""

from __future__ import annotations

import json
import sys
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

RAIZ = Path(__file__).resolve().parents[3]
if str(RAIZ / "sdk" / "python") not in sys.path:
    sys.path.insert(0, str(RAIZ / "sdk" / "python"))

from portal_automacoes import eventos as contrato  # noqa: E402

from modules.catalog.domain.manifest import parse_automation_manifest  # noqa: E402
from modules.dispatch.application.use_cases.job_tokens import IssueJobToken  # noqa: E402
from modules.dispatch.infrastructure.repositories.sqlalchemy_job_tokens import SqlAlchemyJobTokenStore  # noqa: E402
from modules.orchestration.application.use_cases.direct import StartDirectAttempt  # noqa: E402
from modules.orchestration.infrastructure.adapters import build_orchestration_adapters  # noqa: E402
from modules.telemetry.application.dto import EventBatchCommand  # noqa: E402
from modules.telemetry.application.use_cases import IngestExecutionEventBatch  # noqa: E402
from modules.telemetry.infrastructure.adapters import build_telemetry_adapters  # noqa: E402

MANIFESTO = {
    "schema_version": "1.0",
    "automation": {"id": "dominio.integracao_contabil", "name": "Integração Contábil", "version": "2.0.0"},
    "runtime": {"id": "python-desktop", "version": "3.12"},
    "entrypoint": {"type": "python-module", "module": "dominio_folha.cli"},
    "execution": {"mode": "tela"},
    "itens": {"nome": "Empresa", "chave": "codigo", "grupo": "matriz_codigo",
              "atributos": {"type": "object", "properties": {"codigo": {"type": "string"},
                                                             "matriz_codigo": {"type": "string"},
                                                             "separar_por_custo": {"type": "boolean"}}},
              "afetam_trabalho": ["separar_por_custo"]},
    "etapas": [
        {"chave": "iniciar", "nome": "Iniciar", "por_item": False},
        {"chave": "trocar_empresa", "nome": "Trocar empresa"},
        {"chave": "rubricas", "nome": "Rubricas", "por_tarefa": True},
        {"chave": "txt", "nome": "Integração (TXT)", "por_tarefa": True},
        {"chave": "aviso", "nome": "Aviso", "por_item": False},
    ],
}


def novo(prefixo: str) -> str:
    return f"{prefixo}_{uuid.uuid4().hex[:12]}"


def automacao(db: Session) -> tuple[int, int]:
    """Categoria, automação, versão e manifesto normalizado. Devolve (automation_id, version_id)."""
    sufixo = uuid.uuid4().hex[:8]
    categoria = db.execute(text("INSERT INTO categories (name, slug, is_active) VALUES (:n, :s, true) RETURNING id"),
                           {"n": f"Folha {sufixo}", "s": f"folha-{sufixo}"}).scalar_one()
    automation_id = db.execute(text(
        "INSERT INTO automations (name, slug, category_id, executor_type, default_priority, timeout_seconds, max_retries,"
        " is_active, status) VALUES (:n, :s, :c, 'agent', 'normal', 3600, 0, true, 'active') RETURNING id"),
        {"n": f"Integração Contábil {sufixo}", "s": f"integracao-{sufixo}", "c": categoria}).scalar_one()
    manifesto, resultado = parse_automation_manifest(json.dumps(MANIFESTO))
    assert resultado.is_valid, resultado.errors
    version_id = db.execute(text(
        "INSERT INTO automation_versions (automation_id, version, manifest, runtime_id, entrypoint_type, entrypoint,"
        " artifact_bucket, artifact_object_key, artifact_size, artifact_sha256)"
        " VALUES (:a, '2.0.0', CAST(:m AS jsonb), 'python-desktop', 'python-module', CAST(:e AS jsonb), 'local', 'x', 1, :h)"
        " RETURNING id"),
        {"a": automation_id, "m": json.dumps(manifesto.normalized), "e": json.dumps(manifesto.entrypoint),
         "h": "0" * 64}).scalar_one()
    manifest_id = str(uuid.uuid4())
    db.execute(text(
        "INSERT INTO automation_manifests (id, automation_version_id, schema_version, raw_content, normalized_content,"
        " content_hash, validation_status, validator_version)"
        " VALUES (:i, :v, '1.0', :r, CAST(:n AS jsonb), :h, 'valid', 'catalog-v1')"),
        {"i": manifest_id, "v": version_id, "r": json.dumps(MANIFESTO), "n": json.dumps(manifesto.normalized),
         "h": manifesto.content_hash})
    db.execute(text("UPDATE automation_versions SET manifest_id = :m WHERE id = :v"), {"m": manifest_id, "v": version_id})
    db.commit()
    return automation_id, version_id


def execucao(db: Session, version_id: int, criada_em: datetime) -> tuple[str, str]:
    execution_id, job_id = novo("exe"), novo("tsk")
    db.execute(text("INSERT INTO orchestration_executions (id, type, origin, status, created_at)"
                    " VALUES (:i, 'automation', 'manual', 'running', :c)"), {"i": execution_id, "c": criada_em})
    db.execute(text("INSERT INTO task_executions (id, execution_id, automation_version_id, status)"
                    " VALUES (:i, :e, :v, 'running')"), {"i": job_id, "e": execution_id, "v": version_id})
    db.commit()
    return execution_id, job_id


def maquina(db: Session, nome: str | None = None) -> str:
    machine_id = novo("mch")
    db.execute(text("INSERT INTO machines (id, name) VALUES (:i, :n)"), {"i": machine_id, "n": nome or machine_id})
    db.commit()
    return machine_id


@dataclass
class Agente:
    agent_id: str
    instance_id: str
    machine_id: str


def agente(db: Session, machine_id: str) -> Agente:
    agent_id, instance_id = novo("agt"), novo("agi")
    db.execute(text("INSERT INTO agents (id, name, hostname, connectivity_status, administrative_status, health_status,"
                    " occupancy_status, machine_id) VALUES (:i, :i, 'dp01', 'online', 'enabled', 'healthy', 'idle', :m)"),
               {"i": agent_id, "m": machine_id})
    db.execute(text("INSERT INTO agent_instances (id, agent_id, process_started_at) VALUES (:i, :a, now())"),
               {"i": instance_id, "a": agent_id})
    db.commit()
    return Agente(agent_id, instance_id, machine_id)


def tentativa_agente(db: Session, job_id: str, ag: Agente, numero: int = 1) -> str:
    attempt_id = novo("att")
    db.execute(text("INSERT INTO execution_attempts (id, task_execution_id, attempt_number, status, agent_id, agent_instance_id,"
                    " executor_type, executor_id, machine_id) VALUES (:i, :t, :n, 'running', :a, :ai, 'agent', :a, :m)"),
               {"i": attempt_id, "t": job_id, "n": numero, "a": ag.agent_id, "ai": ag.instance_id, "m": ag.machine_id})
    db.execute(text("UPDATE task_executions SET current_attempt_number = :n WHERE id = :t"), {"n": numero, "t": job_id})
    db.commit()
    return attempt_id


def instancia_direta(db: Session, automation_id: int, machine_id: str, status: str = "aprovada") -> str:
    instance_id = novo("dri")
    db.execute(text("INSERT INTO direct_instances (id, automation_id, machine_id, status) VALUES (:i, :a, :m, :s)"),
               {"i": instance_id, "a": automation_id, "m": machine_id, "s": status})
    db.commit()
    return instance_id


def tentativa_direta(db: Session, job_id: str, instance_id: str, machine_id: str,
                     duracao: timedelta = timedelta(hours=12)) -> tuple[str, str]:
    """Tentativa pelo caso de uso real e token pelo emissor real. Devolve (attempt_id, token)."""
    agora = datetime.now(UTC)
    adapters = build_orchestration_adapters(db)
    tentativa = StartDirectAttempt(adapters.tasks, adapters.attempts).execute(
        task_execution_id=job_id, direct_instance_id=instance_id, machine_id=machine_id, package_id=None, now=agora)
    token = IssueJobToken(SqlAlchemyJobTokenStore(db)).execute(
        task_execution_id=job_id, execution_attempt_id=tentativa.id, direct_instance_id=instance_id, now=agora,
        duracao=duracao)
    db.commit()
    return tentativa.id, token


@dataclass
class Roteiro:
    """Eventos do contrato com horários controlados (para medir durações exatas)."""

    inicio: datetime
    eventos: list[dict[str, Any]] = field(default_factory=list)
    agora: datetime | None = None

    def __post_init__(self) -> None:
        self.agora = self.inicio

    def passar(self, segundos: float) -> "Roteiro":
        self.agora += timedelta(seconds=segundos)
        return self

    def emitir(self, tipo: str, **payload: Any) -> "Roteiro":
        evento = contrato.montar(len(self.eventos) + 1, tipo, payload)
        evento["occurred_at"] = self.agora.isoformat().replace("+00:00", "Z")
        contrato.validar(evento)
        self.eventos.append(evento)
        return self

    def etapa(self, chave: str, segundos: float, *, item: str | None = None, tarefas: int | None = None,
              previstas: int | None = None, situacao: str = "ok") -> "Roteiro":
        self.emitir("etapa.iniciada", etapa=chave, item=item,
                    tarefas_previstas=previstas if previstas is not None else tarefas)
        self.passar(segundos)
        return self.emitir("etapa.concluida", etapa=chave, item=item, situacao=situacao, tarefas=tarefas)


def empresa(r: Roteiro, codigo: str, *, separa: bool, centros: int, seg_troca: float, seg_por_centro: float,
            txt: bool = True, atencao: bool = False) -> Roteiro:
    r.emitir("item.iniciado", item=codigo, rotulo=f"Empresa {codigo}", grupo=codigo,
             configuracao={"separar_por_custo": separa})
    r.etapa("trocar_empresa", seg_troca, item=codigo)
    r.etapa("rubricas", seg_por_centro * centros, item=codigo, tarefas=centros)
    if atencao:
        r.emitir("atencao", item=codigo, motivo="Rubricas a parametrizar",
                 tabela={"colunas": [{"chave": "codigo", "titulo": "Rubrica"}], "linhas": [{"codigo": 8781}]})
        return r.emitir("item.concluido", item=codigo, situacao="atencao", resumo="1 rubrica a parametrizar")
    if txt:
        r.etapa("txt", seg_por_centro * centros / 2, item=codigo, tarefas=centros)
    return r.emitir("item.concluido", item=codigo, situacao="ok", resumo="TXT gerado")


def enviar_pelo_agente(db: Session, attempt_id: str, ag: Agente, eventos: list[dict[str, Any]], inicio_seq: int = 1) -> Any:
    """Mesmo caminho do gateway do Agent: execution.event.batch com automation.event."""
    adapters = build_telemetry_adapters(db)
    lote = [{"event_id": f"{uuid.uuid4()}:1", "event_sequence": inicio_seq + i, "event_type": "automation.event",
             "occurred_at": e["occurred_at"], "payload": e} for i, e in enumerate(eventos)]
    return IngestExecutionEventBatch(
        adapters.attempts, adapters.events, adapters.acknowledgements, adapters.metrics, adapters.validator,
        adapters.masker, adapters.realtime, adapters.transaction, projector=adapters.projector,
    ).execute(EventBatchCommand(execution_attempt_id=attempt_id, events=lote, agent_id=ag.agent_id,
                                agent_instance_id=ag.instance_id))


def publicar(db: Session, version_id: int) -> None:
    """Runtime e pacote publicados: a versão pode entrar na fila (regra real do Catalog)."""
    runtime_id, versao_runtime, objeto, pacote = novo("rtm"), novo("rtv"), novo("obj"), novo("pkg")
    db.execute(text("INSERT INTO runtimes (id, key, name, status) VALUES (:i, :k, 'Python desktop', 'published')"),
               {"i": runtime_id, "k": f"python-desktop-{runtime_id}"})
    db.execute(text("INSERT INTO runtime_versions (id, runtime_id, version, operating_system, architecture, status)"
                    " VALUES (:i, :r, '3.12', 'windows', 'x64', 'published')"), {"i": versao_runtime, "r": runtime_id})
    db.execute(text("INSERT INTO stored_objects (id, bucket, object_key, content_type, provider, status)"
                    " VALUES (:i, 'local', :k, 'application/zip', 'local', 'available')"), {"i": objeto, "k": f"{objeto}.zip"})
    db.execute(text("INSERT INTO automation_packages (id, automation_version_id, stored_object_id, package_format, file_name,"
                    " size_bytes, sha256, status) VALUES (:i, :v, :o, 'zip', 'pacote.zip', 1, :h, 'published')"),
               {"i": pacote, "v": version_id, "o": objeto, "h": "0" * 64})
    db.execute(text("UPDATE automation_versions SET status = 'published', package_id = :p, runtime_version_id = :r"
                    " WHERE id = :v"), {"p": pacote, "r": versao_runtime, "v": version_id})
    db.commit()


def instancia_com_sinal(db: Session, instance_id: str, quando: datetime | None = None) -> None:
    db.execute(text("UPDATE direct_instances SET last_seen_at = :q WHERE id = :i"),
               {"q": quando or datetime.now(UTC), "i": instance_id})
    db.commit()
