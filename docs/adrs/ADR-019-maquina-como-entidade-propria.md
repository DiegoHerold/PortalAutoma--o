# ADR-019 - Máquina como entidade própria

Status: aceito em 09/11/2026.

## Contexto

Hoje a máquina é implícita no Agent. Com o modo direto (ADR-018), uma máquina pode ter
Agent, instâncias diretas ou os dois, e a regra de ocupação precisa valer para todos.

## Decisao

`Machine` passa a ser uma entidade do contexto Fleet, cadastrada pelo administrador. O
Agent e cada instância direta apontam para a máquina.

A ocupação depende do **modo de execução da automação**, obrigatório no registro:

- `tela`: no máximo um job por máquina, somando os dois modos de conexão. A trava usa a
  chave `machine:{id}:screen`, e a máquina aparece como "ocupada por <automação>".
- `navegador` e `segundo_plano`: seguem a capacidade do pool da máquina.

O Agent não tem prioridade sobre a instância direta. A diferença entre os modos é o
transporte (uma conexão centralizada) e a verificação do pacote, que só o Agent faz.

## Alternativas consideradas

- Manter a máquina dentro do Agent: a trava não alcançaria instâncias diretas.
- Uma trava por modo de conexão: permitiria duas automações de tela na mesma sessão.

## Consequencias

O manifesto passa a exigir o modo de execução; a ausência deixa de virar
`background` e passa a ser erro de validação. Toda tentativa grava a máquina, para
permitir comparar máquinas no futuro (sem ajustar a estimativa por máquina agora).

## Riscos

Agents já registrados precisam ser associados a uma máquina. A migração cria uma
máquina por Agent existente.

## Impacto de migracao

Tabela `machines` nova; `agents.machine_id` anulável e preenchido pela migração.
