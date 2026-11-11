# ADR-018 - Modo direto de conexão

Status: aceito em 09/11/2026. Complementa o ADR-002 e o ADR-005.

## Contexto

Algumas automações precisam rodar em máquinas sem o Automation Agent, ou já existem
como programas próprios (por exemplo, a Integração Contábil). O ADR-002 trata o Agent
como o único execution plane, e o ADR-005 define uma conexão por Agent.

## Decisao

Existem dois tipos de executor:

- **Agent** (modo agente): a automação fala só com o Agent local; o Agent mantém uma
  única conexão de saída com o Portal (ADR-005 continua valendo).
- **Instância direta** (modo direto): a combinação automação + máquina. Ela fala direto
  com o Portal, também só por conexão de saída (HTTPS), com identidade própria.

O contrato de eventos da automação (`contracts/automation-events/v1`) e o SDK são os
mesmos nos dois modos. Trocar de modo é configuração, não código.

Regras do modo direto:

- Inscrição com código de uso único, aprovada por um administrador, que escolhe a
  máquina. O nome informado pela automação não é prova de identidade.
- Credencial por instância: par de chaves gerado na máquina, chave privada protegida por
  DPAPI com escopo do usuário. Desafio assinado trocado por token de curta duração.
- Escopo mínimo: registrar, receber os próprios jobs, enviar eventos e arquivos dos
  próprios jobs e receber os próprios comandos.
- Token por job, com validade e escopo daquele job.
- Revogação imediata e quarentena (conecta, mas não recebe jobs).
- Toda instância direta é **não gerenciada**: o Portal não verifica a integridade do
  código. A tela mostra isso e a versão informada.
- A instância direta não negocia oferta: recebe o job já reservado. `ExecutionOffer`
  continua exclusiva do Agent, e oferta rejeitada continua não sendo falha (ADR-007).

## Alternativas consideradas

- Exigir o Agent em todas as máquinas: impede automações existentes e máquinas onde o
  Agent não pode ser instalado.
- Abrir porta de entrada na máquina para o Portal chamar a automação: proibido.
- Credencial compartilhada entre automações: proibido.

## Consequencias

`execution_attempts`, `execution_events`, `resource_reservations` e `resource_locks`
passam a referenciar um executor genérico (`executor_type` + `executor_id`), com as
colunas de Agent anuláveis. A migração é aditiva.

## Riscos

No modo direto, o Portal não impede que alguém abra outra automação de tela
manualmente na mesma sessão do Windows. O Agent consegue. Para automações de tela, o
modo agente é o recomendado.

## Impacto de migracao

Nenhum dado é apagado. Execuções existentes ficam com `executor_type = agent`.
