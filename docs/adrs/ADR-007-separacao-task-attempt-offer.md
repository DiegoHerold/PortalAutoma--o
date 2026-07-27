# ADR-007 - Separacao entre Task, Attempt e Offer

Status: aceito.

## Contexto

Uma unica entidade de execucao nao representa corretamente solicitacao, tarefa,
tentativa fisica e negociacao com Agent.

## Decisao

Usar `Execution`, `TaskExecution`, `ExecutionAttempt` e `ExecutionOffer`.

## Alternativas consideradas

- Manter `Job` como entidade unica.
- Usar uma unica state machine para tudo.

## Consequencias

Retry cria nova tentativa. Oferta rejeitada nao e falha da automacao. Aceite
nao inicia execucao sem commit.

## Riscos

Frontend e relatorios podem confundir rejeicao de oferta com falha se o
mapeamento legado nao for explicito.

## Impacto de migracao

`Job` e `Execution` legado serao lidos por adaptadores ate as novas tabelas
`executions`, `task_executions`, `execution_attempts` e `execution_offers`
existirem.
