# ADR-009 - Capabilities Tipadas

Status: aceito.

## Contexto

Strings simples nao carregam versao, atributos, status, validade nem origem da
observacao.

## Decisao

Capabilities usam objetos tipados com `key`, `status`, `version`,
`attributes` e `observed_at`.

## Alternativas consideradas

- Lista de strings.
- Campos booleanos por software.

## Consequencias

Manifest pode expressar requisitos ricos. O Portal faz filtro preliminar e o
Agent valida localmente.

## Riscos

Conversao automatica de strings antigas pode perder detalhes de versao e
atributos.

## Impacto de migracao

Capabilities em string continuam aceitas por adaptador e devem ser
normalizadas para objetos tipados.
