# ADR-015 - Estados Multidimensionais do Agent

Status: aceito.

## Contexto

O estado legado `Worker.status` mistura conectividade, saude, administracao e
ocupacao.

## Decisao

Separar estados do Agent em conectividade, administrativo, saude e ocupacao
calculada.

## Alternativas consideradas

- Manter `online`, `busy`, `offline`, `disabled` em um unico campo.
- Calcular tudo apenas no frontend.

## Consequencias

`busy` nao substitui conectividade. Heartbeat nao sobrescreve politica
administrativa. Ocupacao deriva de pools, reservas, locks e execucoes.

## Riscos

Durante a transicao, telas legadas podem continuar exibindo status simples e
precisar de mapeamento claro.

## Impacto de migracao

`Worker.status` sera mantido como campo compatibilidade ate novas colunas ou
tabelas de Agent/Fleet existirem.

