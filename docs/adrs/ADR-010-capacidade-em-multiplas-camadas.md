# ADR-010 - Capacidade em Multiplas Camadas

Status: aceito.

## Contexto

Capacidade observada, recomendada, historica e politica administrativa mudam em
ritmos diferentes.

## Decisao

Separar `MachineProfile`, `AgentRecommendation`, `AdministratorPolicy`,
`CurrentCapacity` e `HistoricalCapacity`.

## Alternativas consideradas

- Um unico `max_concurrency`.
- Heartbeat sobrescrever configuracao manual.

## Consequencias

Scheduler deve considerar pools, reservas, locks e TTL dos snapshots.
Configuracao manual nao e sobrescrita automaticamente.

## Riscos

Snapshots expirados podem induzir o Scheduler a selecionar Agents sem
capacidade real.

## Impacto de migracao

`max_concurrency` legado permanece como fallback ate pools, snapshots,
recomendacoes e politicas administrativas serem persistidos.
