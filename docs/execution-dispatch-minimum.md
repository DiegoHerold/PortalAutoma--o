# Execution e Dispatch minimo

Este documento registra a migracao do Prompt 4A: criar uma execucao, selecionar um Agent compativel, enviar `execution.offer`, receber aceite ou rejeicao, enviar `execution.commit` apos aceite e aceitar `execution.started` como inicio real.

## Inventario

| Componente legado | Arquivo | Responsabilidade | Conceito oficial | Contexto de destino | Acao | Endpoint consumidor | Tela afetada | Teste existente |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Job | `backend/app/models/job.py` | Projecao de solicitacao/queue para frontend legado | Execution | orchestration | KEEP | `/api/v1/jobs` | Jobs | `backend/tests/tasks/test_job_tasks.py` |
| Execution legada | `backend/app/models/execution.py` | Resultado/log legado por Job | ExecutionAttempt/result futuro | orchestration/telemetry | KEEP | `/api/v1/executions` legado | Executions | nenhum direto |
| JobDispatcherService | `backend/app/services/job_dispatcher_service.py` | Antes criava Job e escolhia Worker | CreateAutomationExecution | orchestration/dispatch | REFACTOR | `/api/v1/jobs`, webhooks, triggers | Jobs | service/task legado |
| ExecutionService | `backend/app/services/execution_service.py` | Consulta da tabela legada `executions` | GetExecutionDetails | orchestration | DEFER | `/api/v1/executions` legado | Executions | nenhum direto |
| Worker selection | `backend/app/services/job_dispatcher_service.py` | Selecionava Worker por preferencias | AgentSelectionPort | dispatch/fleet | REPLACE | `/api/v1/jobs` | Jobs | nenhum direto |
| AgentCommand | `backend/modules/dispatch/infrastructure/orm/models.py` | Fila duravel para comandos do Agent | AgentCommand | dispatch | KEEP | Agent Gateway | nenhuma | arquitetura |
| Agent Gateway | `backend/gateway/agent_gateway/message_router.py` | Transporte WS e deduplicacao inbox | Handlers para use cases | gateway | REFACTOR | `/api/v1/agent-gateway/connect` | nenhuma | smoke gateway |

## Escolhas

- A tabela legada `executions` foi preservada; a entidade oficial usa `orchestration_executions` para evitar colisao e perda de dados.
- `TaskExecution` nao recebe estados de oferta ou commit; esses estados ficam em `ExecutionAttempt` e `ExecutionOffer`.
- O Portal permanece em `committed` apos enviar `execution.commit`; `execution.started` aceita `committed` e grava `preparing_at` e `started_at`. Um ACK especifico de commit podera mover para `preparing` em etapa futura.
- `execution.offer` e `execution.commit` seguem os schemas existentes em `contracts/messages/portal-to-agent`.
- `execution.completed`, logs, progresso, timeline, artefatos e batch de eventos continuam fora do escopo do Prompt 4A.
