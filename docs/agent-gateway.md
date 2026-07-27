# Agent Gateway

O endpoint oficial e:

```text
/api/v1/agent-gateway/connect
```

O Agent autentica com `Authorization: Bearer <public_identifier>:<secret>`. O segredo e retornado uma unica vez no registro ou rotacao e armazenado no Portal apenas como hash.

## Handshake

Primeira mensagem do Agent:

```json
{
  "message_type": "agent.connect",
  "payload": {
    "agent_id": "agt_x",
    "agent_instance_id": "agi_y",
    "agent_version": "1.0.0",
    "supported_protocol_versions": ["1.0"]
  }
}
```

O Gateway responde `agent.connected` com protocolo selecionado, politica de heartbeat, hora do Portal e versao desejada.

## Mensagens aceitas nesta etapa

- `agent.connected`
- `agent.resumed`
- `agent.heartbeat`
- `agent.profile.updated`
- `agent.capacity.updated`
- `agent.capabilities.updated`
- `agent.diagnostic.result`
- `agent.update.progress`
- `agent.command.ack`

Mensagens de execucao sao reconhecidas como contrato existente, mas retornam `MESSAGE_TYPE_NOT_SUPPORTED` ate o Prompt 4.

## Fonte de verdade

O WebSocket nao e fonte de verdade. O estado oficial fica no PostgreSQL:

- `agents`
- `agent_instances`
- `agent_connections`
- `agent_resource_snapshots`
- `agent_capabilities`
- `agent_pools`
- `agent_commands`
- `inbox_messages`
- `outbox_messages`

O Connection Manager mantem sockets em memoria somente para entrega rapida. Em reconexao, comandos pendentes sao lidos do banco e reenviados.

## Health e readiness

- `GET /api/v1/agent-gateway/health`: processo ativo.
- `GET /api/v1/agent-gateway/readiness`: PostgreSQL acessivel e repositorios carregaveis.
