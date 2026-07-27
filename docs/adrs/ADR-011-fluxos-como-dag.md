# ADR-011 - Fluxos como DAG

Status: aceito.

## Contexto

Fluxos precisam ser confiaveis antes de um editor visual complexo.

## Decisao

Fluxos comecam como DAGs com dependencias, paralelismo, condicoes simples,
mappings, retries, timeout, cancelamento e skip.

## Alternativas consideradas

- Editor estilo n8n como primeira entrega.
- Linguagem visual completa.

## Consequencias

A primeira entrega prioriza execucao ponta a ponta. Editor visual complexo fica
para depois.

## Riscos

Reaproveitar triggers encadeados como fluxo oficial pode esconder dependencias
e estados insuficientes.

## Impacto de migracao

Triggers encadeados atuais seguem como compatibilidade ate `Flow`,
`FlowVersion` e `FlowExecution` existirem.
