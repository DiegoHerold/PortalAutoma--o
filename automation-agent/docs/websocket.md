# Conexão WebSocket persistente com o Portal

> Incremento 2 da Fase 3 (seção 11 do brief). Uma única conexão WebSocket por processo
> do Agent — não confundir com HTTP (registro, Incremento 1) nem com upload de
> artefatos (HTTPS, Incremento 6).

## Componentes

```
Agent.Domain
  Enums/ConnectionState.cs            Disconnected, Connecting, Authenticating,
                                       Connected, Reconnecting, Degraded, Disabled
  StateMachines/ConnectionStateMachine.cs   transições válidas + IsOperational()
  Models/Connections/ConnectionStatus.cs    ConnectionStatus, ConnectionEvent
  Contracts/IWebSocketTransport.cs          abstração de baixo nível (testável)
  Contracts/IPortalConnectionManager.cs     contrato público consumido pelo resto do Agent
  Contracts/IConnectionStateRepository.cs   persistência de status + histórico

Agent.Infrastructure
  WebSockets/ClientWebSocketTransport.cs    implementação real (System.Net.WebSockets)
  Persistence/PortalConnectionRepository.cs upsert em portal_connections,
                                             append-only em connection_events

Agent.Application
  Connection/ConnectionBackoffCalculator.cs backoff exponencial com full jitter
  Connection/PortalConnectionManager.cs     orquestra conectar/autenticar/bombear/cair/reconectar
  Connection/PortalConnectionHostedService.cs  ponte para o Generic Host
```

## Máquina de estados

```
Disconnected ──► Connecting ──► Authenticating ──► Connected ──► Reconnecting ──┐
     ▲                │               │                 │            │         │
     │                ▼               ▼                 ▼            ▼         │
     └──────────── Disconnected  Disconnected        Degraded    Disconnected  │
                                                          │                     │
                                                          └────────► Connected ◄┘
Qualquer estado ──► Disabled ──► Disconnected (reabilitado)
```

Ponto de desenho deliberado: **`Disconnected → Reconnecting` não existe**.
"Reconectando" só faz sentido depois de ter estado `Connected` ao menos uma vez. A
primeira tentativa de conexão (ex.: logo após o boot, antes do registro terminar) vai
sempre por `Disconnected → Connecting`, nunca por `Reconnecting`. `PortalConnectionManager`
é o único dono das transições — `MainLoopAsync` decide *quando* tentar de novo (backoff),
nunca *para qual* estado ir.

`Degraded` está definido na máquina de estados mas o `PortalConnectionManager` do
Incremento 2 não o usa diretamente — ele representa "socket aberto, mas o Portal não
está respondendo direito" e é hoje só considerado pelo health check do heartbeat
(`docs/heartbeat.md`), não pela conexão em si. Incrementos futuros podem decidir mover a
conexão para `Degraded` de fato; a máquina de estados já suporta isso sem mudança de
schema.

## Reconexão

- Backoff exponencial com jitter total (seção 11): `delay = random(0, min(initial * 2^(tentativa-1), máximo))`,
  piso de 100ms para nunca virar busy-loop.
- Cada tentativa de reconexão usa uma instância **nova** de `IWebSocketTransport` — um
  socket morto nunca é reaproveitado.
- Uma conexão que caiu depois de ter ficado `Connected` reseta o contador de tentativas:
  a primeira nova tentativa é imediata; só volta a ter backoff se essa também falhar.

## Garantia de conexão única

`RunAsync` usa um `SemaphoreSlim(1,1)` com `WaitAsync(0, ct)` (não bloqueante) — uma
segunda chamada enquanto a primeira está ativa lança `InvalidOperationException`
imediatamente, em vez de abrir um segundo socket. Isso é reforçado por teste
(`SecondRunAsyncCall_WhileFirstIsActive_ThrowsInvalidOperationException`).

## Envio de mensagens

`TrySendAsync` é **best-effort, não bloqueante**: grava numa fila em memória
(`Channel<string>`) e retorna. Se a conexão não estiver operacional (nenhum socket
ativo agora) ou a fila estiver cheia, retorna `false` e a mensagem é descartada por
esta camada — sem retenção nem retry aqui. Entrega garantida (persistir antes de
enviar, reenviar depois de reconectar) é responsabilidade do Outbox, que chega no
Incremento 3. Isso é intencional: `PortalConnectionManager` não duplica a
responsabilidade do Outbox nem inventa uma segunda fila persistente.

## Watchdog de silêncio

O `ClientWebSocket` cuida do ping/pong de protocolo via `KeepAliveInterval`, mas isso
não cobre o caso clássico de rede que caiu sem FIN/RST (o socket TCP fica "meio
aberto"). Por isso `PortalConnectionManager` roda um watchdog de aplicação: se nenhum
tráfego (mensagem recebida) chegar por `max(ConnectionTimeoutSeconds,
HeartbeatIntervalSeconds * 3)`, a conexão é considerada parada e derrubada
proativamente, disparando reconexão.

## Configuração (`PortalOptions`)

| Campo | Uso no Incremento 2 |
|---|---|
| `WebSocketUrl` | endpoint `wss://` — `agent_id` e `installation_id` vão como query string |
| `ConnectionTimeoutSeconds` | timeout do handshake e piso do watchdog |
| `HeartbeatIntervalSeconds` | intervalo do heartbeat (`docs/heartbeat.md`) e insumo do watchdog |
| `ReconnectInitialSeconds` / `ReconnectMaximumSeconds` | parâmetros do backoff |
| `RequireSecureTransport` | exige `wss://` (só desative em teste local) |

## Testes

`tests/Agent.IntegrationTests/Connection/PortalConnectionManagerTests.cs` usa
`FakeWebSocketTransport`/`FakeWebSocketTransportFactory`
(`tests/Agent.IntegrationTests/Helpers/FakeWebSocketTransport.cs`) — sem rede real, mas
exercitando exatamente a mesma classe que roda em produção.

| Teste obrigatório | Cobertura |
|---|---|
| `websocket-connect` | `Connect_ReachesConnectedState_WithBearerAuthHeader` |
| `websocket-reconnect` | `ConnectionDrop_TriggersReconnect_WithFreshTransportInstance` |
| `websocket-single-connection` | `SecondRunAsyncCall_WhileFirstIsActive_ThrowsInvalidOperationException` |

Cobertura adicional: `Connect_WithoutRegisteredIdentity_StaysDisconnectedAndRetries`
(não tenta abrir socket sem `agent_id`/credencial), `HandshakeFailure_IsRetried_UntilItSucceeds`.

Unitários: `tests/Agent.UnitTests/StateMachines/ConnectionStateMachineTests.cs`,
`tests/Agent.UnitTests/Connection/ConnectionBackoffCalculatorTests.cs`.

## CLI

- `portal status` — agora também inclui um bloco `connection` com o snapshot em memória
  do processo atual (`IPortalConnectionManager.GetStatus()`).
- `portal connection-events` — histórico recente de `connection_events` (sobrevive a
  reinícios, útil para depurar quedas).

Não existe comando para controlar remotamente um Agent já em execução como Windows
Service a partir de uma segunda invocação de CLI (isso exigiria um canal de controle
local, ex. Named Pipe, que não faz parte deste incremento). Os comandos acima são
diagnóstico do processo em que rodam.
