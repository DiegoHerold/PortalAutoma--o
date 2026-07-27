# Fluxos do Sistema

Status: superseded para arquitetura, preservado como compatibilidade historica.

O fluxo antigo `Webhook -> Dispatcher -> Worker -> Celery -> WebSocket` nao e
mais a arquitetura oficial para novas implementacoes. Ele descreve partes do
comportamento legado ainda presentes no codigo e deve ser consultado apenas
durante a migracao.

Use estes documentos como fonte oficial:

- `docs/architecture.md`
- `docs/domain-model.md`
- `docs/execution-lifecycle.md`
- `docs/protocol.md`
- `docs/scheduler.md`
- `docs/reliability.md`
- `docs/migration.md`

## Fluxo oficial de execucao

```mermaid
flowchart TB
    Manual["Manual/API/Schedule/Flow"] --> Execution["Execution"]
    Execution --> Task["TaskExecution"]
    Task --> Scheduler["Scheduler: compatibilidade, disponibilidade, score"]
    Scheduler --> Attempt["ExecutionAttempt"]
    Attempt --> Offer["ExecutionOffer"]
    Offer --> AgentDecision{"Agent aceita?"}
    AgentDecision -- nao --> Rejection["Registra rejeicao e tenta outro Agent"]
    AgentDecision -- sim --> Commit["execution.commit"]
    Commit --> Run["Agent prepara e executa"]
    Run --> Events["Eventos estruturados"]
    Events --> State["Orchestration valida transicoes"]
    State --> Artifact["Artefato disponivel"]
```

## Fluxo DAG

```mermaid
flowchart LR
    A["Task A"] --> B["Task B"]
    A --> C["Task C"]
    B --> D["Task D"]
    C --> D
    D --> E["Task E"]
```

Fluxos devem comecar como DAGs confiaveis. Editor visual complexo e loops
recursivos ficam fora do primeiro marco funcional.
