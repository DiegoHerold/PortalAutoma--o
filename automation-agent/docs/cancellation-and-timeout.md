# Cancelamento e Timeout

## Timeout

```mermaid
graph LR
    RUN[Running] -->|timeout_seconds| TO[TIMED_OUT]
    TO --> CANCEL[Solicitar cancelamento]
    CANCEL --> WAIT[Aguardar graceful_shutdown_seconds]
    WAIT -->|Encerrou| DONE[Resultado coletado]
    WAIT -->|Não encerrou| FORCE[TerminateJobObject]
    FORCE --> DONE
```

## Cancelamento

```mermaid
graph LR
    REQ[CANCEL_REQUESTED] --> ING[CANCELLING]
    ING --> GRACEFUL[Cancelamento gracioso]
    GRACEFUL -->|OK| CANCELLED
    GRACEFUL -->|Timeout| FORCE[Encerramento forçado via Job Object]
    FORCE --> CANCELLED
```

## Implementação

O `CancellationManager` cria um `CancellationTokenSource` vinculado:
- Ao token do caller (shutdown do Agent)
- Com timeout configurado

O `ProcessTreeManager` executa:
1. Aguarda `gracefulTimeoutMs`
2. Se não encerrou: `TerminateJobObject` (toda a árvore)
3. Confirma encerramento com `WaitForExit(3000)`

## Registro

Cada cancelamento registra:
- Quem solicitou (agent, timeout, usuário)
- Quando foi solicitado
- Duração do cancelamento
- Se encerramento forçado foi necessário
