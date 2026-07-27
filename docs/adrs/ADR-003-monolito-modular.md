# ADR-003 - Monolito Modular

Status: aceito.

## Contexto

O Portal ainda esta em fase de formacao de dominio e nao deve assumir custo de
microsservicos prematuramente.

## Decisao

O Portal comeca como monolito modular com contextos Access, Catalog, Fleet,
Orchestration, Dispatch, Telemetry, Storage e Governance.

## Alternativas consideradas

- Microsservicos por contexto desde o inicio.
- Camada unica de services/repositories sem fronteiras.

## Consequencias

Processos podem ser separados (API, Gateway, Workers, Scheduler), mas
compartilham repositorio, contratos internos e banco. Fronteiras devem ser
protegidas por testes arquiteturais.

## Riscos

Sem testes de fronteira, o monolito modular pode voltar a ser apenas uma
camada unica de services e repositories.

## Impacto de migracao

`backend/modules/` comeca como fronteira documentada. Arquivos legados serao
movidos em etapas com adaptadores de import.
