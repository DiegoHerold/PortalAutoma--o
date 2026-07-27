# Ciclo de Vida de Execucao

Status: vigente.

## Oferta, aceite e commit

```mermaid
sequenceDiagram
    participant P as Portal
    participant A as Agent
    P->>A: execution.offer
    A->>A: valida sessao, CPU, memoria, disco, locks e capabilities
    alt aceita
        A-->>P: execution.accepted
        P->>P: cria/ativa lease e reserva
        P->>A: execution.commit
        A->>A: prepara runtime e pacote
        A-->>P: execution.started
    else rejeita
        A-->>P: execution.rejected
        P->>P: encerra oferta e tenta outro Agent conforme politica
    end
```

## Transicoes

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

Regras:

- `accepted` nao significa `running`.
- O Agent nao inicia antes de receber `execution.commit`.
- Rejeicao de oferta nao falha a automacao.
- Retry cria nova `ExecutionAttempt`.
- Estado persistente muda por caso de uso de Orchestration/Dispatch.

## Cancelamento

```mermaid
sequenceDiagram
    participant U as Usuario/API
    participant P as Portal
    participant A as Agent
    U->>P: cancel execution
    P->>P: valida estado e registra comando
    P->>A: execution.cancel
    A->>A: encerra processo e recursos locais
    A-->>P: execution.cancelled
    P->>P: libera lease, locks e reservas
```

## Upload de artefatos

```mermaid
sequenceDiagram
    participant A as Agent
    participant P as Portal
    participant S as S3
    A-->>P: artifact.created
    P-->>A: upload URL temporaria
    A->>S: upload HTTPS
    A-->>P: artifact.available
    P->>P: persiste Artifact
```

