# Orchestration

Ownership: execucoes, tarefas, tentativas, retries, timeout, cancelamento,
fluxos, agendamentos, dependencias e resultados.

Legado a migrar:

- `app/models/job.py`
- `app/models/execution.py`
- `app/models/schedule.py`
- `app/models/trigger.py`
- `app/services/execution_service.py`
- `app/services/schedule_service.py`
- `app/tasks/schedule_tasks.py`

`Job` e adaptador temporario para `Execution`/`TaskExecution`.

