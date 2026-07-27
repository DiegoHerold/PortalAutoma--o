# Maquinas de Estado

Status: vigente.

Estados oficiais tambem estao publicados em `contracts/executions/states.json`.
Transicoes funcionais serao implementadas em etapa posterior; este documento
define os limites.

## AutomationVersion

```mermaid
stateDiagram-v2
    [*] --> draft
    draft --> validating
    validating --> published
    validating --> blocked
    published --> deprecated
    published --> blocked
    deprecated --> blocked
```

Estados: `draft`, `validating`, `published`, `deprecated`, `blocked`.

Regras:

- Versao publicada e imutavel.
- Correcao gera nova versao.
- Versao usada por execucao nao pode ser removida.

## Execution

```mermaid
stateDiagram-v2
    [*] --> created
    created --> pending
    pending --> running
    running --> succeeded
    running --> partially_succeeded
    running --> failed
    running --> cancelling
    cancelling --> cancelled
    running --> timed_out
```

Estados: `created`, `pending`, `running`, `succeeded`,
`partially_succeeded`, `failed`, `cancelling`, `cancelled`, `timed_out`.

## TaskExecution

```mermaid
stateDiagram-v2
    [*] --> pending
    pending --> ready
    ready --> queued
    queued --> running
    running --> succeeded
    running --> failed
    running --> cancelled
    running --> timed_out
    ready --> skipped
```

Estados proibidos em TaskExecution: `offered`, `accepted`, `committed`,
`rejected`, `expired`.

## ExecutionAttempt

```mermaid
stateDiagram-v2
    [*] --> created
    created --> offered
    offered --> accepted
    offered --> rejected
    offered --> expired
    accepted --> committed
    committed --> preparing
    preparing --> running
    preparing --> failed
    running --> succeeded
    running --> failed
    running --> cancelled
    running --> timed_out
    running --> lost
```

Cada retry cria uma nova tentativa. Tentativas anteriores nao sao
sobrescritas.

## ExecutionOffer

```mermaid
stateDiagram-v2
    [*] --> pending
    pending --> accepted
    pending --> rejected
    pending --> expired
    accepted --> committed
    pending --> cancelled
    accepted --> cancelled
```

Oferta rejeitada nao e falha da automacao.

## Agent

Agent possui estados multidimensionais.

```mermaid
stateDiagram-v2
    state "Conectividade" as Connectivity {
        [*] --> connecting
        connecting --> online
        online --> stale
        stale --> disconnected
        disconnected --> offline
        stale --> online
    }
    state "Administrativo" as Administrative {
        [*] --> pending_registration
        pending_registration --> enabled
        enabled --> draining
        enabled --> maintenance
        enabled --> updating
        enabled --> disabled
    }
    state "Saude" as Health {
        [*] --> healthy
        healthy --> degraded
        degraded --> error
        degraded --> healthy
    }
    state "Ocupacao Calculada" as Occupancy {
        [*] --> idle
        idle --> busy
        busy --> saturated
        busy --> idle
    }
```

`busy` nao substitui conectividade. Heartbeat nao sobrescreve politica
administrativa.

## Sequencias

Command sequence:

```text
agent_id + command_sequence
```

Event sequence:

```text
execution_attempt_id + event_sequence
```

Nao reutilize uma unica sequencia para comandos e eventos.
