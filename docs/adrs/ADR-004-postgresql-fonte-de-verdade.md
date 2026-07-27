# ADR-004 - PostgreSQL como Fonte de Verdade

Status: aceito.

## Contexto

Execucoes e eventos precisam sobreviver a quedas, reconexoes e duplicidade de
mensagens.

## Decisao

PostgreSQL e a fonte oficial para catalogo, fleet, execucoes, tentativas,
ofertas, comandos, leases, eventos, outbox e inbox.

## Alternativas consideradas

- Estado em memoria.
- Redis como fonte oficial.
- Broker como fonte oficial.

## Consequencias

Redis, Celery e WebSocket sao transporte/cache/execucao interna. Toda transicao
oficial precisa ser persistida.

## Riscos

Modelar persistencia demais antes da fatia vertical pode atrasar validacao do
fluxo real.

## Impacto de migracao

Migrations futuras devem criar tabelas para Agent, Attempt, Offer, Lease,
eventos, inbox, outbox e command log sem apagar dados legados.
