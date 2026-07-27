# Contexto para Agentes de Desenvolvimento

Status: vigente.

Este repositorio implementa o Portal de Automacoes. O Portal e o Control Plane
do ecossistema; o Automation Agent e o Execution Plane.

## Regras arquiteturais

- O Portal decide o que precisa ser executado.
- O Portal seleciona Agents candidatos.
- O Agent realiza a validacao final de admissao.
- O Agent pode rejeitar uma execucao mesmo apos selecao pelo Portal.
- O Portal e a fonte oficial dos estados persistentes e globais.
- O Agent e a fonte das observacoes locais da maquina e dos processos.
- WebSocket, SSE, Redis, Celery e mensageria sao transporte ou aceleracao, nao
  fonte oficial de verdade.
- A arquitetura do Portal e um monolito modular.
- Nao criar microsservicos prematuramente.
- Nao implementar etapas futuras sem instrucao explicita.
- Preservar o design atual do frontend. Nao reconstruir, redesenhar ou apagar
  telas sem solicitacao explicita.
- Reutilizar backend existente quando compativel; mover/refatorar antes de
  substituir.
- Nao criar mocks para esconder integracoes ausentes.

## Contextos oficiais

- Access.
- Catalog.
- Fleet.
- Orchestration.
- Dispatch.
- Telemetry.
- Storage.
- Governance.

## Ownership

Consulte `docs/domain-model.md` e `docs/modules.md`. Apenas o contexto
proprietario altera diretamente sua entidade. Outros contextos usam casos de
uso, comandos internos ou contratos.

## Contratos

Contratos versionados ficam em `contracts/`. Nao duplique manualmente schemas
divergentes no Portal e no Agent.

Mensagens Portal-Agent devem possuir `protocol_version`, `message_id`,
`message_type`, `sent_at`, `agent_id`, `agent_instance_id` e `payload`.

## Modelo de execucao

Nao use uma entidade unica para tudo. Separe:

- `Execution`
- `TaskExecution`
- `ExecutionAttempt`
- `ExecutionOffer`

`TaskExecution` nao recebe estados de oferta. Oferta rejeitada nao e falha da
automacao. O Agent nao inicia execucao antes de `execution.commit`.

## Compatibilidade

O codigo atual ainda usa `Worker`, `Job` e `Execution` legado. Trate esses
nomes como adaptadores temporarios conforme `docs/migration.md`, desde que
chamem a nova camada de aplicacao e nao dupliquem regra de dominio.

## Frontend

Consulte `docs/frontend-integration.md` antes de alterar qualquer chamada de
API do frontend. Ajustes visuais estao fora do escopo desta etapa.
