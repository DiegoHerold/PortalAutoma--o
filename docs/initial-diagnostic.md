# Diagnostico Inicial

Status: registro da inspecao feita antes das alteracoes de alinhamento.

## Arquitetura atual

O workspace ativo contem o Portal de Automacoes como monolito com backend
FastAPI, frontend Next.js, PostgreSQL, Redis, Celery, Nginx e storage local/S3.
O Automation Agent externo nao esta presente como segundo repositorio neste
workspace. O Portal possui endpoints e servicos de gateway para Agent em
`backend/app/api/v1/endpoints/agents.py` e
`backend/app/services/agent_gateway_service.py`.

## Tecnologias encontradas

- Backend: FastAPI.
- ORM: SQLAlchemy 2.
- Migrations: Alembic.
- Banco: PostgreSQL.
- Fila/execucao interna atual: Celery.
- Cache/pubsub atual: Redis.
- Frontend: Next.js, React, TypeScript e Tailwind.
- Infra: Docker Compose, Nginx, Flower, Redis e PostgreSQL.
- Storage: implementacoes local e S3/MinIO.
- Auth: JWT, roles e permissoes por categoria.

## Componentes encontrados

- API REST, WebSocket de frontend e WebSocket de Agent.
- Modelos legados `Worker`, `Job` e `Execution`.
- Catalogo com `Automation`, `AutomationSource` e `AutomationVersion`.
- Empacotamento imutavel em `backend/app/domain/automation_package.py`.
- Manifest parser em `backend/app/domain/automation_manifest.py`.
- Storage local/S3 em `backend/app/integrations/storage/`.
- Schedules, triggers, auditoria, roles e permissoes.
- Frontend operacional para dashboard, automacoes, execucoes, jobs, workers e
  settings.

## Funcionalidades reutilizaveis

- AutomationVersion publicada e imutavel.
- Hash SHA-256 do pacote.
- Download por URL temporaria ou URL pre-assinada.
- Importacao GitHub/ZIP convergindo para o mesmo pacote.
- Autenticacao, autorizacao e auditoria.
- Realtime para frontend.
- WebSocket unico do Agent no gateway atual.

## Inconsistencias

- `Worker` mistura Agent logico, instancia, conectividade, saude e ocupacao.
- `Job` mistura solicitacao, fila e tarefa logica.
- `Execution` mistura tentativa fisica, resultado e protocolo.
- `execution.assign` inicia execucao sem oferta/aceite/commit explicitos.
- Queda de WebSocket marca trabalhos como falha imediata.
- Capabilities sao listas de strings.
- Eventos do Agent viram logs de texto, sem sequencia, ACK, deduplicacao ou
  gaps.
- Redis e Celery aparecem em documentos antigos como parte central do fluxo de
  execucao, mas nao podem ser fonte de verdade.

## Conceitos duplicados

- Worker e Agent.
- Job e Execution.
- Execution e Attempt.
- Command, Event e Log.
- Flow, chained trigger e integracao n8n.
- `automation.package_url` legado e `AutomationVersion` publicada.

## Lacunas

- Contratos versionados compartilhados.
- Envelope de protocolo com `message_id`.
- `AgentInstance`.
- `ExecutionOffer`.
- `ExecutionLease`.
- Outbox, inbox e command log persistentes.
- State machines explicitas.
- Capacity model por pools.
- Scheduler explicavel por compatibilidade, disponibilidade e classificacao.

## Dependencias inadequadas

- Handlers do Agent ainda fazem alteracoes de status no fluxo legado.
- Services legados acessam modelos de varios dominios sem fronteira formal.
- Status e maquinas de estado ainda aparecem como strings em constantes e
  schemas.
- Redis/Celery sao usados operacionalmente, mas precisam permanecer fora da
  fonte oficial de verdade.
- Plano de migracao para frontend e endpoints legados.

## Riscos de migracao

- Dados existentes em `workers`, `jobs` e `executions`.
- Dependencia do Agent atual na mensagem `execution.assign`.
- Frontend acoplado a nomes e status legados.
- Automacoes antigas ainda podem depender de `automation.package_url`.
- Mudanca brusca no protocolo pode interromper execucoes reais.

## Plano incremental de alteracao

1. Fixar arquitetura oficial em docs e ADRs.
2. Criar `contracts/` versionado.
3. Criar fronteiras logicas e fisicas leves em `backend/modules/`.
4. Manter `backend/app/` funcional enquanto adaptadores sao introduzidos.
5. Migrar Catalog primeiro, pois `AutomationVersion` e pacotes ja existem.
6. Migrar Fleet/Agent com adaptador para `Worker`.
7. Migrar Orchestration/Dispatch separando `Job`, `ExecutionAttempt` e
   `ExecutionOffer`.
8. Introduzir Telemetry estruturado, inbox/outbox e command log.
9. Renomear UX e endpoints somente apos compatibilidade estar pronta.

## Arquivos alterados nesta tarefa

Ver `git status --short` ao final da execucao para a lista real. O escopo
planejado inclui README, docs oficiais, contratos, ADRs, plano de migracao e
testes arquiteturais documentais.
