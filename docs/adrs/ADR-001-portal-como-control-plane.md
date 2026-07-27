# ADR-001 - Portal como Control Plane

Status: aceito.

## Contexto

O sistema precisa de um ponto oficial para catalogo, politicas, execucoes,
ofertas, eventos e artefatos.

## Decisao

O Portal e o control plane. Ele decide o que executar, seleciona Agents
candidatos, mantem o estado persistente oficial e recebe eventos/artefatos.

## Alternativas consideradas

- Agent escolher trabalho por conta propria.
- Redis ou fila como fonte de verdade.

## Consequencias

O Portal precisa de state machines, command log, inbox/outbox e persistencia
forte. O Agent nao cria execucoes oficiais.

## Riscos

Concentrar decisoes no Portal pode criar services grandes se as fronteiras de
contexto nao forem respeitadas.

## Impacto de migracao

`Job`, `Worker` e `Execution` legados permanecem como adaptadores ate os novos
modelos persistentes existirem.
