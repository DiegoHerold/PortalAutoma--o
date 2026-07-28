# Database (SQLite)

## Tabelas

| Tabela | Fase | Descrição |
|--------|------|-----------|
| schema_migrations | 1 | Controle de versão do schema |
| agent_identity | 1 | Identidade persistente |
| agent_state | 1 | Estado atual do Agent |
| agent_state_transitions | 1 | Histórico de transições |
| machine_profiles | 1 | Snapshots do perfil da máquina |
| resource_samples | 1 | Amostras de recursos |
| capabilities | 1 | Capabilities detectadas |
| executions | 1 | Execuções (contrato para Fase 2) |
| execution_state_transitions | 1 | Transições de execução (Fase 2) |
| outbox_events | 1 | Fila de saída (Fase 2) |
| inbox_commands | 1 | Fila de entrada (Fase 2) |

## Migrations

Versionadas numericamente. Idempotentes. Executadas em transação.
