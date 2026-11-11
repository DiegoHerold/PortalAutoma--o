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
- Nao apagar telas sem solicitacao explicita. O redesenho autorizado e o do
  ADR-020, feito por fase.
- Reutilizar backend existente quando compativel; mover/refatorar antes de
  substituir.
- Nao criar mocks para esconder integracoes ausentes.
- O frontend esta sendo refeito com a identidade Biason (ADR-020, que substitui o
  ADR-017). Siga `docs/design-system.md` e a fase vigente; nao misture o visual antigo
  com o novo na mesma tela.
- Ha dois modos de conexao (ADR-018): modo agente (a automacao fala so com o Agent
  local) e modo direto (a automacao fala direto com o Portal). Nos dois, nenhuma
  maquina abre porta de entrada, e o contrato de eventos e o mesmo.
- Maquina e entidade propria (ADR-019). Automacao de tela ocupa a maquina sozinha,
  somando os dois modos.
- "Worker" designa apenas processos internos do Portal (Celery). Na interface, use
  "Maquina" e "Agent".

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

Eventos emitidos pela automacao (etapa, item, progresso, log, passo, atencao,
espera, pausa) seguem `contracts/automation-events/v1/` e sao os mesmos nos dois
modos. O SDK Python fica em `sdk/python/`.

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
API do frontend. O redesenho segue o ADR-020 e o plano de fases em
`docs/fase-0-diagnostico-orquestracao.md`.
