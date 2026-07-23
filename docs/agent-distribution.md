# Distribuição para o Automation Agent (não implementado nesta sessão)

Por decisão explícita do usuário, esta sessão implementou **apenas o lado
Portal** do catálogo de automações. O executável/processo do Automation Agent
que roda nas máquinas Windows e realmente executa o código da automação não
foi construído aqui — só a parte do Portal que o alimenta (empacotamento,
storage, resolução de qual pacote entregar) foi feita, reaproveitando o
gateway de Agent que já existia no repositório.

## O que já existe e funciona (pré-existente, não tocado além do resolver)

- `app/api/v1/endpoints/agents.py` e `agent_gateway_service.py`: registro de
  Agent (`Worker` faz esse papel), heartbeat, fila de comandos via
  WebSocket `/agents/ws`, claim/finish de comando.
- Com a mudança em `automation_package_resolver.py`, qualquer automação com
  uma `AutomationVersion` publicada já é resolvida corretamente nesse fluxo.

## O que falta para um Agent real consumir isso

1. Um instalador/serviço Windows que mantenha a conexão WebSocket viva e
   implemente o protocolo de register/heartbeat/claim/finish.
2. Download do pacote (URL assinada, local ou S3) + verificação de
   `package_sha256` antes de extrair.
3. Isolamento de dependências por automação (ex.: venv por
   `automation_id`/`version`, nunca instalação global) — requisito de
   segurança explícito do spec original.
4. Carregamento do entrypoint (`module.callable`) e execução com o payload
   do job, com timeout de `execution.timeout_seconds`.
5. Suporte a `execution.interactive_session: true` (session-runner) para
   automações que precisam de um processo de longa duração com
   entrada/saída incremental — protocolo de eventos ainda por desenhar em
   detalhe.

## Recomendação de próximo passo

Tratar isso como uma fase separada, com seu próprio levantamento de requisitos
(linguagem/runtime do instalador, política de atualização do próprio Agent,
como ele é distribuído para os desktops Windows). O catálogo implementado
aqui já deixa o lado servidor pronto para quando essa fase começar.
