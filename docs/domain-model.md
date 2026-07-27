# Modelo de Dominio

Status: vigente para novas implementacoes.

## Entidades por contexto

Catalog:

- `Automation`
- `AutomationVersion`
- `AutomationManifest`
- `AutomationPackage`
- `Runtime`
- `RuntimeVersion`

Fleet:

- `Agent`
- `AgentInstance`
- `AgentCapability`
- `AgentResourceSnapshot`
- `AgentConfiguration`

Orchestration:

- `Execution`
- `TaskExecution`
- `ExecutionAttempt`
- `FlowExecution`
- `ScheduleExecution`

Dispatch:

- `ExecutionOffer`
- `ResourceReservation`
- `ResourceLock`
- `ExecutionLease`

Telemetry:

- `ExecutionEvent`
- `ExecutionLog`
- `ExecutionMetric`
- `EventAcknowledgement`

Storage:

- `Artifact`
- `UploadSession`
- `StoredObject`

Governance:

- `Secret`
- `SecretVersion`
- `SecretGrant`
- `AuditEvent`

## Automation

Representa a identidade logica e permanente de uma automacao.

Campos conceituais:

- `id`
- `key`
- `name`
- `description`
- `category`
- `tags`
- `status`
- `created_by`
- `created_at`
- `updated_at`

Exemplos de chave:

- `dominio.importar_documentos`
- `portal.baixar_documentos`
- `documentos.validar_arquivos`

Nome da automacao nao e identidade tecnica.

## AutomationVersion

Representa uma versao imutavel.

Estados:

- `draft`
- `validating`
- `published`
- `deprecated`
- `blocked`

Campos conceituais:

- `id`
- `automation_id`
- `version`
- `status`
- `manifest`
- `package_id`
- `release_notes`
- `published_by`
- `published_at`
- `deprecated_at`
- `blocked_at`

Regras:

- Uma versao publicada nao pode ser alterada.
- Uma correcao deve gerar nova versao.
- Uma versao usada por execucoes nao pode ser removida.
- Execucoes devem referenciar versoes especificas.

## Execution

Representa uma solicitacao completa.

Tipos:

- `automation`
- `flow`

Origens:

- `manual`
- `api`
- `schedule`
- `flow`
- `retry`
- `reprocess`
- `system`

Estados:

- `created`
- `pending`
- `running`
- `succeeded`
- `partially_succeeded`
- `failed`
- `cancelling`
- `cancelled`
- `timed_out`

Campos principais:

- `id`
- `type`
- `origin`
- `status`
- `requested_by`
- `input`
- `result`
- `created_at`
- `started_at`
- `completed_at`

## TaskExecution

Representa uma tarefa logica dentro de uma Execution. Uma execucao de fluxo
pode possuir varias tarefas.

Estados:

- `pending`
- `ready`
- `queued`
- `running`
- `succeeded`
- `failed`
- `cancelled`
- `timed_out`
- `skipped`

TaskExecution nao contem estados de negociacao com Agent.

## ExecutionAttempt

Representa uma tentativa fisica em uma maquina. Cada retry cria uma nova
tentativa.

Estados:

- `created`
- `offered`
- `accepted`
- `committed`
- `preparing`
- `running`
- `succeeded`
- `failed`
- `cancelled`
- `timed_out`
- `lost`
- `rejected`
- `expired`

Campos principais:

- `agent_id`
- `agent_instance_id`
- `attempt_number`
- `runtime_version_id`
- `package_id`
- `lease_id`
- `offered_at`
- `accepted_at`
- `committed_at`
- `started_at`
- `completed_at`
- `exit_code`
- `error_code`
- `error_message`
- `resource_usage`

Tentativas anteriores nao podem ser sobrescritas.

## ExecutionOffer

Representa a oferta enviada pelo Portal a um Agent candidato.

Estados:

- `pending`
- `accepted`
- `rejected`
- `expired`
- `committed`
- `cancelled`

Campos principais:

- `id`
- `execution_attempt_id`
- `agent_id`
- `status`
- `offered_at`
- `expires_at`
- `responded_at`
- `rejection_code`
- `rejection_details`

Oferta rejeitada nao e falha da automacao.

## Agent e AgentInstance

`Agent` representa uma instalacao logica e permanece o mesmo entre
reinicializacoes.

`AgentInstance` representa uma execucao especifica do processo do Agent. Cada
inicializacao gera novo identificador.

Eventos e comandos devem informar ambos:

- `agent_id`
- `agent_instance_id`

## Compatibilidade com legado

Durante a migracao:

- `Worker` e adaptador para `Agent`.
- `Job` e adaptador para `Execution` ou `TaskExecution`, conforme origem.
- `Execution` legado e adaptador para `ExecutionAttempt`.
- `Automation.package_url` e fallback temporario para `AutomationVersion`
  publicada.
