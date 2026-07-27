# Roadmap

Status: vigente.

## Fase 1 - Inspecao e alinhamento

- Analisar repositorios disponiveis.
- Corrigir documentacao.
- Definir contextos.
- Definir ownership.
- Definir contratos.
- Definir IDs.
- Definir maquinas de estado.
- Definir envelope.
- Definir versionamento de protocolo.

## Fase 2 - Fundacao de confiabilidade

- PostgreSQL.
- Migrations.
- Outbox.
- Inbox.
- Command log.
- Idempotencia.
- S3 ou MinIO.

## Fase 3 - Catalogo minimo

- Automation.
- AutomationVersion.
- Manifest.
- Package.
- Runtime.
- Publicacao imutavel.

## Fase 4 - Fleet e Gateway

- Registro seguro.
- Agent.
- AgentInstance.
- Heartbeat.
- Capabilities.
- Capacidade.
- WebSocket.
- Reconexao.

## Fase 5 - Primeira execucao completa

```text
manual -> queued -> offer -> accepted -> commit -> preparing -> running -> completed
```

## Fase 6 - Confiabilidade operacional

- ACK.
- Reenvio.
- Leases.
- Cancelamento.
- Timeout.
- Agent perdido.
- Recuperacao apos reinicializacao.
- Eventos fora de ordem.

## Fase 7 - Scheduler inteligente

- Filtros.
- Scoring.
- Afinidade.
- Locks.
- Reservas.
- Concorrencia.
- Rejeicoes.
- Backoff.

## Fase 8 - Interface operacional

- Agents.
- Execucoes.
- Timeline.
- Logs.
- Metricas.
- Artefatos.
- Diagnosticos.

## Fase 9 - Fluxos

- DAG.
- Dependencias.
- Paralelismo.
- Mappings.
- Condicoes.
- Retries.

## Fase 10 - Agendamentos

- Execucao unica.
- Recorrencia.
- Timezone.
- Idempotencia.
- Historico.

## Fase 11 - Governanca e evolucao

- Segredos.
- Auditoria.
- Retencao.
- Recomendacoes de recursos.
- Redis, caso necessario.
- Broker, caso necessario.
- Extracao de servicos, caso necessaria.

