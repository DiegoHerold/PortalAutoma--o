# Inventario de Migracao - Catalog, Storage e Governance

Status: vigente para a Etapa 4/5.

| Componente legado | Arquivo | Responsabilidade | Contexto de destino | Acao | Endpoint consumidor | Tela frontend | Teste existente |
|---|---|---|---|---|---|---|---|
| Automation ORM | `backend/app/models/automation.py` | Tabela ativa de automacoes | Catalog infrastructure | KEEP/REFACTOR | `/automations` | Automacoes, Jobs, Triggers, Schedules | arquitetura |
| AutomationVersion ORM | `backend/app/models/automation_version.py` | Tabela ativa de versoes | Catalog infrastructure | KEEP/REFACTOR | `/automations/{id}/versions` | Detalhe da automacao | arquitetura |
| AutomationSource ORM | `backend/app/models/automation_source.py` | Origem GitHub/upload | Catalog infrastructure | KEEP/MOVE gradual | `/automations/{id}/sources` | Detalhe da automacao | indireto |
| AutomationService | `backend/app/services/automation_service.py` | CRUD legado de automacoes | Catalog application | REFACTOR | `/automations` | Automacoes | arquitetura |
| AutomationImportService | `backend/app/services/automation_import_service.py` | Confirmacao de staging | Catalog application | REFACTOR | `/automations/import/{id}/confirm` | Import GitHub/ZIP | arquitetura |
| AutomationVersionLifecycleService | `backend/app/services/automation_version_lifecycle_service.py` | publicar/deprecar/sync | Catalog application | REFACTOR | `:activate`, `:deprecate`, `:sync` | Detalhe da automacao | arquitetura |
| ManualUploadService | `backend/app/services/manual_upload_service.py` | Upload ZIP direto usado pelo frontend | Catalog/Storage | REFACTOR | `/automations/import/upload` | Nova automacao ZIP | dominio legado |
| GithubDiscoveryService | `backend/app/services/github_discovery_service.py` | Descoberta e staging GitHub | Catalog infrastructure | REFACTOR | `/integrations/github/*` | Nova automacao GitHub | dominio legado |
| Manifest parser legado | `backend/app/domain/automation_manifest.py` | Parser antigo | Catalog domain | MOVE/REPLACE gradual | import GitHub/ZIP | Import GitHub/ZIP | dominio legado |
| Package builder legado | `backend/app/domain/automation_package.py` | Montagem ZIP e extracao segura basica | Catalog package validation | REFACTOR | import GitHub/ZIP | Import ZIP/GitHub | dominio legado |
| Package storage legado | `backend/app/integrations/storage/*` | Local/S3 para pacotes | Storage infrastructure | KEEP/ADAPTER | import, dispatch download | Import/detail | storage legado |
| AuditLog legado | `backend/app/models/audit.py` | Auditoria historica | Governance | KEEP/ADAPTER | `/audit` | Auditoria | services |
| GitHub client | `backend/app/integrations/github/client.py` | Acesso GitHub App | Catalog infrastructure | KEEP/PORT futuro | `/integrations/github/*` | Integracoes/GitHub import | dominio legado |
| Celery catalog tasks | `backend/app/tasks/*` | Nao ha task dedicada de Catalog | Telemetry/Workers futuro | DEFER | n/a | n/a | n/a |
| Worker/Job | `backend/app/models/worker.py`, `backend/app/models/job.py` | Execucao/dispatch legado | Fleet/Orchestration/Dispatch | DEFER | `/workers`, `/jobs` | Workers, Jobs | existente |

## Decisoes

- `automations` e `automation_versions` continuam como tabelas ativas para nao
  duplicar conceitos.
- Novas entidades oficiais de manifesto, pacote, runtime, storage,
  confiabilidade, idempotencia e auditoria foram adicionadas em tabelas
  separadas.
- `backend/app` permanece como compatibilidade: rotas antigas delegam para
  casos de uso em `backend/modules/catalog`.
- GitHub discovery e upload ZIP ainda ficam como producers temporarios de
  staging, mas a confirmacao passou para `ConfirmStagedAutomationImport`.

## Itens Deferidos

- Fleet, Agent Registry, Gateway WebSocket e delivery de `AgentCommand`.
- Migração completa da tela de Jobs/Workers para Execution/Agent.
- Remocao fisica de services legados enquanto ainda houver consumidores.
