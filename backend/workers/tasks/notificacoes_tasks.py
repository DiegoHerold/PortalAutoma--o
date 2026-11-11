"""Tarefas periódicas da Fase 6: detectar ocorrências, enviar e-mails e aplicar a retenção."""

from __future__ import annotations

from infrastructure.database import SessionLocal
from workers.celery_app import celery_app


@celery_app.task(name="workers.tasks.notificacoes_tasks.detectar")
def detectar() -> dict[str, int]:
    from modules.telemetry.infrastructure.adapters.notificacoes import build_detectar

    with SessionLocal() as db:
        return build_detectar(db).execute()


@celery_app.task(name="workers.tasks.notificacoes_tasks.enviar")
def enviar() -> dict[str, int]:
    from modules.telemetry.infrastructure.adapters.notificacoes import build_enviar

    with SessionLocal() as db:
        return build_enviar(db).execute()


@celery_app.task(name="workers.tasks.notificacoes_tasks.aplicar_retencao")
def aplicar_retencao() -> list[dict]:
    from modules.telemetry.infrastructure.adapters.notificacoes import build_aplicar_retencao

    with SessionLocal() as db:
        return build_aplicar_retencao(db).execute()
