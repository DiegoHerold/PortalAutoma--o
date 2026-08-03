# Heartbeat (`agent.heartbeat`)

> Incremento 2 da Fase 3 (seção 16 do brief).

## Componentes

```
Agent.Protocol/Messages/HeartbeatPayload.cs      payload de wire (agent_id, version,
                                                  state, connection_state, capacity,
                                                  resources, interactive_session,
                                                  running_executions, outbox_pending,
                                                  pending_artifacts)
Agent.Application/Heartbeat/HeartbeatSnapshotBuilder.cs  compõe o payload a partir de
                                                  serviços já existentes (Fases 1/2)
Agent.Application/Heartbeat/HeartbeatService.cs  BackgroundService: envia periodicamente,
                                                  rastreia o último ack
```

`HeartbeatSnapshotBuilder` **não coleta nada novo** — só agrega o que
`ICapacityManager`, `IResourceMonitor`, `IAgentStateManager`, `IExecutionManager` e
`IMachineProfileRepository` já expõem das Fases 1 e 2. Isso é deliberado: a seção 1 do
brief proíbe recriar telemetria que já existe.

## Ciclo

1. `HeartbeatService.ExecuteAsync` dispara o primeiro heartbeat imediatamente ao
   iniciar (não espera um ciclo inteiro de `HeartbeatIntervalSeconds`), depois segue em
   `PeriodicTimer(HeartbeatIntervalSeconds)`.
2. Cada tick chama `IPortalConnectionManager.TrySendAsync("agent.heartbeat", payload, correlationId)`.
   Se a conexão não estiver operacional (`ConnectionStateMachine.IsOperational`), o
   envio é pulado silenciosamente — não há fila própria de heartbeat; o próximo tick
   tenta de novo.
3. Ao receber `agent.heartbeat_ack` (via o mesmo `IPortalConnectionManager.MessageReceived`
   usado por qualquer mensagem do Portal), `HeartbeatService` atualiza `LastAckAtUtc`.

## Campos ainda não preenchidos (por design, não por esquecimento)

- `outbox_pending` e `pending_artifacts` são enviados como `0` — o Outbox
  (Incremento 3) e o upload de artefatos (Incremento 6) ainda não existem. Quando
  existirem, `HeartbeatService` passa a consultá-los em vez do valor fixo.
- `interactive_session.available` é sempre `false` — sem Session Runner (Incremento 7+)
  o Agent não tem como saber se existe sessão interativa.

## Health checks

Dois componentes novos em `HealthCheckRunner` (além de `agent_registration`, do
Incremento 1):

- **`websocket`** — `Healthy` quando `Connected`; `Degraded` quando `Degraded`,
  `Disabled`, ou tentando conectar; `Unhealthy` quando `ReconnectAttempt >= 5` (tentando
  e falhando repetidamente).
- **`heartbeat`** — distingue "socket caiu" (já coberto por `websocket`) de "socket de
  pé, mas o Portal não confirma o heartbeat": `Degraded` quando o tempo desde o último
  `agent.heartbeat_ack` (ou desde o último envio, se nunca houve ack) excede
  `HeartbeatIntervalSeconds * 3`.

Ambos retornam `Healthy` quando `Portal.Enabled = false` — Agent em modo local não deve
reportar problema de conectividade que não existe.

## Testes

`tests/Agent.IntegrationTests/Connection/HeartbeatServiceTests.cs`:

| Teste obrigatório | Cobertura |
|---|---|
| `heartbeat` | `HeartbeatService_SendsHeartbeatPayload_OnceConnected`, `HeartbeatAck_FromPortal_UpdatesLastAckTimestamp` |

O primeiro teste parseia a mensagem realmente enviada pelo `FakeWebSocketTransport` e
confirma `message_type = agent.heartbeat` e `agent_id` correto. O segundo injeta um
`agent.heartbeat_ack` sintético pelo transporte falso e confirma que
`HeartbeatService.LastAckAtUtc` é atualizado — a mesma validação de envelope
(`EnvelopeValidator`) usada para mensagens reais do Portal.
