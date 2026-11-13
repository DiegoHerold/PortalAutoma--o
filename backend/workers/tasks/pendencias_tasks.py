"""Pendências (13/11/2026): abre as pendências dos itens em atenção e avisa quem pediu a execução
quando a automação não mandou o e-mail dela com o botão "Continuar processo"."""

from __future__ import annotations

from infrastructure.database import SessionLocal
from workers.celery_app import celery_app


@celery_app.task(name="workers.tasks.pendencias_tasks.avisar")
def avisar() -> dict[str, int]:
    from modules.orchestration.pendencias.api import pendencias

    with SessionLocal() as db:
        resultado = pendencias(db).avisar_por_padrao()
        db.commit()
        return resultado
