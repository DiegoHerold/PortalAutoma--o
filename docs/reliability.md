# Confiabilidade

Status: vigente.

## Outbox, inbox e command log

Mensagens recebidas do Agent devem ser deduplicadas por `message_id`.

```mermaid
flowchart LR
    UseCase["Caso de uso"] --> DB[("PostgreSQL")]
    UseCase --> Outbox["Transactional Outbox"]
    Outbox --> Dispatcher["Dispatcher de mensagens"]
    Dispatcher --> Agent["Agent WebSocket"]
    Agent --> Inbox["Inbox"]
    Inbox --> Telemetry["Telemetry"]
    Telemetry --> DB
```

`AgentCommand` e entidade persistente:

```text
AgentCommand
  id
  agent_id
  agent_instance_id
  command_sequence
  message_type
  payload
  status
  created_at
  sent_at
  acknowledged_at
  expires_at
  attempts
  last_error
```

Estados:

- `pending`
- `sent`
- `acknowledged`
- `expired`
- `failed`
- `cancelled`

## Leases

```mermaid
sequenceDiagram
    participant P as Portal
    participant A as Agent
    P->>P: cria ExecutionLease apos commit
    P->>A: execution.commit com lease_id
    loop durante execucao
        A-->>P: lease.renewed
        P->>P: atualiza renewed_at/expires_at
    end
```

Se o lease expirar:

1. Marque a tentativa como suspeita.
2. Aguarde periodo de tolerancia.
3. Consulte o Agent quando possivel.
4. Reconcilie estado.
5. Marque `lost` somente quando necessario.
6. Aplique retry conforme politica.
7. Evite duplicidade enquanto houver risco real de execucao ainda viva.

Nao faca retry imediato por perda momentanea de WebSocket.

## WebSocket e HTTPS

WebSocket nao transporta binarios grandes nem grandes spools de eventos.
Downloads, uploads e sincronizacoes extensas usam HTTPS/S3/MinIO.
