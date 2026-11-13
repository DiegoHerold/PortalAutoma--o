from celery import Celery

from infrastructure.config import get_settings

settings = get_settings()

celery_app = Celery(
    "portal_automacoes",
    broker=settings.redis_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.task_default_queue = "normal"
celery_app.conf.task_routes = {
    "workers.tasks.dispatch_tasks.schedule_ready_tasks": {"queue": "normal"},
    "workers.tasks.schedule_tasks.sync": {"queue": "normal"},
}

# Import so Celery Beat (and the worker's task registry) knows about it --
# Beat only schedules tasks that have already been imported/registered.
from workers.tasks import schedule_tasks  # noqa: E402,F401
from workers.tasks import housekeeping_tasks  # noqa: E402,F401
from workers.tasks import dispatch_tasks  # noqa: E402,F401
from workers.tasks import notificacoes_tasks  # noqa: E402,F401
from workers.tasks import correio_tasks  # noqa: E402,F401
from workers.tasks import pendencias_tasks  # noqa: E402,F401

celery_app.conf.beat_schedule = {
    "sync-schedules-every-minute": {
        "task": "workers.tasks.schedule_tasks.sync",
        "schedule": 60.0,
    },
    "detect-stale-agents-every-minute": {
        "task": "workers.tasks.housekeeping_tasks.detect_stale_agents",
        "schedule": 60.0,
    },
    "expire-execution-offers-every-30-seconds": {
        "task": "workers.tasks.housekeeping_tasks.expire_execution_offers",
        "schedule": 30.0,
    },
    "dispatch-queue-every-5-seconds": {
        "task": "workers.tasks.dispatch_tasks.dispatch_queue",
        "schedule": 5.0,
    },
    "schedule-ready-tasks-every-5-seconds": {
        "task": "workers.tasks.dispatch_tasks.schedule_ready_tasks",
        "schedule": 5.0,
    },
    "reconcile-expired-leases-every-15-seconds": {
        "task": "workers.tasks.housekeeping_tasks.reconcile_expired_leases",
        "schedule": 15.0,
    },
    "detect-lost-attempts-every-20-seconds": {
        "task": "workers.tasks.housekeeping_tasks.detect_lost_attempts",
        "schedule": 20.0,
    },
    "force-cancel-executions-every-30-seconds": {
        "task": "workers.tasks.housekeeping_tasks.force_cancel_execution_attempts",
        "schedule": 30.0,
    },
    # Fase 6: notificações (detectar a cada 30 s; e-mail só sai se o envio estiver ligado)
    "detectar-notificacoes-every-30-seconds": {
        "task": "workers.tasks.notificacoes_tasks.detectar",
        "schedule": 30.0,
    },
    "enviar-notificacoes-every-60-seconds": {
        "task": "workers.tasks.notificacoes_tasks.enviar",
        "schedule": 60.0,
    },
    # Retenção por automação: sem prazo definido não apaga nada
    "aplicar-retencao-every-hour": {
        "task": "workers.tasks.notificacoes_tasks.aplicar_retencao",
        "schedule": 3600.0,
    },
    # Limpeza do sistema (notificações, medições, sessões vencidas...): regras em
    # modules/governance/domain/configuracoes.py, prazos em Governança > Retenção
    # E-mail centralizado (13/11/2026): reenvio do que ficou na fila por falha temporária
    # Pendências (13/11/2026): item em atenção vira pendência; sem aviso da automação, e-mail para quem pediu
    "avisar-pendencias-every-30-seconds": {
        "task": "workers.tasks.pendencias_tasks.avisar",
        "schedule": 30.0,
    },
    "reenviar-emails-every-15-seconds": {
        "task": "workers.tasks.correio_tasks.enviar_pendentes",
        "schedule": 15.0,
    },
    "aplicar-limpeza-do-sistema-every-30-minutes": {
        "task": "workers.tasks.housekeeping_tasks.aplicar_limpeza_do_sistema",
        "schedule": 1800.0,
    },
}
celery_app.conf.timezone = "UTC"
