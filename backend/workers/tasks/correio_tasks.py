"""E-mail centralizado (13/11/2026): manda de novo o que ficou na fila por falha temporária do Graph."""

from __future__ import annotations

from infrastructure.database import SessionLocal
from workers.celery_app import celery_app


@celery_app.task(name="workers.tasks.correio_tasks.enviar_pendentes")
def enviar_pendentes() -> dict[str, int]:
    from modules.telemetry.correio.api import build_correio

    with SessionLocal() as db:
        resultado = build_correio(db).enviar_pendentes()
        db.commit()
        return resultado
