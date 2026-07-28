# Admission Controller

Decisão centralizada de aceitar ou rejeitar execuções.

## Avaliação em 4 etapas

```mermaid
graph TD
    REQ[ExecutionRequest] --> S1[1. Estado do Agent]
    S1 -->|READY/DEGRADED| S2[2. Capabilities]
    S1 -->|Outro| REJECT1[Rejeitar: AGENT_NOT_READY]
    S2 -->|OK| S3[3. Capacidade do Pool]
    S2 -->|Falta| REJECT2[Rejeitar: CAPABILITY_NOT_AVAILABLE]
    S3 -->|Slot disponível| S4[4. Reservar]
    S3 -->|Cheio| REJECT3[Rejeitar: POOL_FULL]
    S4 --> ACCEPT[Aceitar com ReservationId]
```

## Motivos de Rejeição

| Código | Retryable | Descrição |
|--------|-----------|-----------|
| `POOL_FULL` | sim | Pool sem slots |
| `GLOBAL_LIMIT_REACHED` | sim | Limite global atingido |
| `INSUFFICIENT_MEMORY` | sim | Memória insuficiente |
| `INSUFFICIENT_DISK` | sim | Disco insuficiente |
| `CAPABILITY_NOT_AVAILABLE` | não | Capability ausente |
| `AGENT_NOT_READY` | sim | Agent não está pronto |
| `AGENT_DRAINING` | sim | Agent está encerrando |
| `INVALID_MANIFEST` | não | Manifesto inválido |

## Decisão

```json
{
  "accepted": true,
  "reservation_id": "res_abc123",
  "pool": "background",
  "slots_reserved": 1
}
```
