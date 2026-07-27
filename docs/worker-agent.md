# Automation Agent

Status: substitui o conceito antigo de Worker Agent.

O Automation Agent e o execution plane. Ele roda na maquina que executa
automacoes, observa recursos locais, valida ofertas, prepara runtime e pacote,
executa, monitora, gera eventos estruturados e envia artefatos.

## Responsabilidades

- Manter identidade local (`agent_id`) e nova instancia por processo
  (`agent_instance_id`).
- Publicar heartbeat e snapshots de recursos.
- Descobrir capabilities tipadas.
- Calcular recomendacao de capacidade.
- Aplicar politica administrativa recebida do Portal sem sobrescreve-la.
- Validar oferta localmente.
- Aceitar ou rejeitar oferta com codigo estruturado.
- Iniciar somente depois de receber `execution.commit`.
- Gerar eventos com sequencia e manter spool offline.
- Baixar pacotes/runtimes por HTTPS e verificar hash/assinatura.
- Fazer upload de artefatos por HTTPS/S3/MinIO.

## O que nao faz

- Nao escolhe automacoes por conta propria.
- Nao cria execucoes oficiais.
- Nao publica pacotes.
- Nao controla fluxos.
- Nao mantem estado global.
- Nao executa codigo diretamente do GitHub.
- Nao envia arquivos grandes pelo WebSocket.

## Compatibilidade

O codigo atual ainda chama parte desse conceito de `Worker`. Durante a migracao,
`Worker` deve funcionar como adaptador de `Agent`, conforme `docs/migration.md`.
