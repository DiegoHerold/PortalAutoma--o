# Outbox e Inbox persistentes

> Incremento 3 da Fase 3. O WebSocket continua sendo apenas transporte; SQLite e a
> camada local de durabilidade.

## Fluxo de saida

```
Agent Service / Execution Host
  -> outbox_events
  -> OutboxBatchSender
  -> WebSocket
  -> Portal
  -> message.ack
  -> outbox_events.status = acknowledged
```

Toda mensagem importante deve ser persistida por `OutboxMessagePublisher` antes de
qualquer tentativa de envio. O sender envia em lotes, preservando `message_id` em replay.
Eventos de execucao com `execution_attempt_id` e `sequence` sao enviados em ordem: uma
sequencia maior nao passa enquanto houver sequencia anterior nao confirmada para a mesma
tentativa.

Estados usados em `outbox_events.status`:

- `pending`: persistida e elegivel para envio.
- `failed`: tentativa anterior nao teve ACK e foi reagendada.
- `sent`: entregue ao loop de envio do WebSocket, aguardando `message.ack`.
- `acknowledged`: confirmada pelo Portal.
- `dead_letter`: nao sera reenviada automaticamente.

Mensagens `sent` sem ACK voltam para replay apos `Messaging.AcknowledgementTimeoutSeconds`.
Ao atingir `Messaging.MaxAttempts`, viram `dead_letter`.

## Fluxo de entrada

```
Portal
  -> WebSocket
  -> inbox_commands
  -> dedupe por message_id
  -> InboxCommandProcessor
  -> handler local
  -> command.ack via Outbox
```

`PortalInboxService` persiste comandos antes do processamento. Duplicatas com o mesmo
`message_id` nao criam nova linha e nao executam duas vezes. Duplicata com payload
diferente gera `protocol.error` via Outbox, mantendo a primeira mensagem persistida.

O dispatcher e plugavel por `IInboxCommandHandler`. Comandos sem handler permanecem
pendentes para incrementos futuros, em vez de fingir sucesso. Falhas repetidas de handler
viram `dead_letter` e geram `command.ack` com esse status.

## ACKs

`message.ack` confirma mensagens do Agent para o Portal. O payload aceita:

- `message_id`
- `message_ids`
- `execution_attempt_id` + `last_contiguous_sequence`

`command.ack` e uma mensagem de saida normal e, portanto, tambem passa pelo Outbox.

## Diagnostico

- `portal status` inclui `messaging.outbox` e `messaging.inbox`.
- `portal messaging` retorna somente os contadores das filas.
- `diagnostics` exporta `messaging-diagnostics.json`.
- O health check `durable_messaging` fica `Degraded` quando ha dead letters.
- O heartbeat agora reporta `outbox_pending` real.
