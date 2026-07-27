# Classificacao do Backend Atual

Status: diagnostico para a reestruturacao incremental.

## KEEP

- FastAPI como framework.
- SQLAlchemy/Alembic/PostgreSQL como base de persistencia.
- JWT/auth/permissoes existentes, a migrar para Access.
- Storage local/S3, a migrar para Storage.
- Validacao estatica de manifesto, movida para Catalog domain como modelo
  oficial.
- Empacotamento imutavel, a migrar para Catalog/Storage.
- Cliente GitHub, a migrar para Catalog infrastructure.

## MOVE

- `app/domain/automation_manifest.py` -> `modules/catalog/domain/manifest.py`.
- `app/domain/automation_package.py` -> Catalog/Storage.
- `app/integrations/storage/*` -> `modules/storage/infrastructure`.
- `app/integrations/github/*` -> `modules/catalog/infrastructure`.
- Auth, users, roles e permissions -> `modules/access`.
- Audit -> `modules/governance`.

## REFACTOR

- `AutomationImportService`: separar casos de uso de Catalog da infraestrutura
  de staging/storage/audit.
- `AutomationService`: agora e facade de compatibilidade e delega CRUD para
  `modules.catalog.application.use_cases`.
- `AutomationVersionLifecycleService`: agora delega publicacao/depreciacao para
  `PublishAutomationVersion` e `DeprecateAutomationVersion`.
- `JobDispatcherService`: substituir logica Worker/Job por Dispatch com
  ExecutionOffer, reservas e leases.
- `AgentGatewayService`: transformar em tradutor de protocolo sem regras de
  dominio.
- `WorkerService`: migrar para Fleet com Agent e AgentInstance.
- Realtime/WebSocket frontend: mover para Telemetry/SSE futuramente.

## REPLACE

- `Job` como entidade oficial.
- `Worker` como entidade oficial.
- `Execution` legado como tentativa/resultado unico.
- `WorkerStatus` unico.
- Capabilities como lista simples de strings.
- `ready`/`invalid` como estados oficiais de `AutomationVersion`; permanecem
  apenas para compatibilidade visual enquanto o frontend e religado.
- `app/services/worker_service.py`: substituido por facade de compatibilidade
  que traduz `/workers` para `Fleet.Agent`.
- `app/services/agent_gateway_service.py`: substituido por facade legada para
  registro/heartbeat; o WebSocket oficial fica em `backend/gateway`.

## DELETE

Somente depois de substituicao funcional:

- Tests que validarem `Job`/`Worker` como dominio oficial.
- Endpoints antigos que nao puderem chamar a nova camada sem duplicar regra.
- Mocks permanentes ou runners demonstrativos sem caminho real de Agent.

## Riscos

- Frontend consome amplamente `/jobs`, `/workers` e tipos legados.
- Migrations atuais ainda descrevem tabelas antigas.
- Testes existentes validam comportamentos legados.
- O Agent externo nao esta neste workspace.
