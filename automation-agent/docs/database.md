# Database (SQLite)

## Tabelas

| Tabela | Migration | Descrição |
|--------|-----------|-----------|
| schema_migrations | 1 | Controle de versão do schema |
| agent_identity | 1 | Identidade persistente |
| agent_state | 1 | Estado atual do Agent |
| agent_state_transitions | 1 | Histórico de transições |
| machine_profiles | 1 | Snapshots do perfil da máquina |
| resource_samples | 1 | Amostras de recursos |
| capabilities | 1 | Capabilities detectadas |
| executions | 1, 2, 3 | Execuções (estendida nas migrations 2 e 3) |
| execution_state_transitions | 1 | Transições de execução |
| outbox_events | 1, 3 | Fila de saída (estendida na 3) |
| inbox_commands | 1, 3 | Fila de entrada (estendida na 3) |
| runtime_artifacts | 2 | Runtimes imutáveis baixados |
| package_artifacts | 2 | Pacotes de automação |
| downloads | 2 | Downloads em andamento |
| execution_attempts | 2 | Tentativas de execução |
| execution_events | 2 | Eventos de execução |
| execution_results | 2 | Resultados |
| resource_reservations | 2 | Reservas de capacidade |
| execution_artifacts | 2 | Artefatos gerados |
| **agent_registration** | **3** | Registro do Agent no Portal |
| **agent_credentials_metadata** | **3** | Metadados da credencial (sem segredo) |
| **agent_credentials_protected** | **3** | Blob protegido por DPAPI |
| **portal_connections** | **3** | Conexões WebSocket |
| **connection_events** | **3** | Transições de estado da conexão |
| **message_acknowledgements** | **3** | ACKs trocados com o Portal |
| **execution_offers** | **3** | Ofertas recebidas e decisão |
| **execution_commits** | **3** | Commits recebidos |
| **execution_leases** | **3** | Leases de execução |
| **session_runners** | **3** | Session Runners registrados |
| **interactive_sessions** | **3** | Sessões Windows observadas |
| **session_events** | **3** | Eventos de sessão e desktop |
| **resource_locks** | **3** | Locks exclusivos de desktop |
| **pending_artifacts** | **3** | Artefatos aguardando upload |
| **artifact_upload_attempts** | **3** | Tentativas de upload |
| **protocol_errors** | **3** | Erros de protocolo |
| **sync_runs** | **3** | Reconciliações após reconexão |

## Migrations

Versionadas numericamente, idempotentes, executadas em transação.
`SqliteDatabaseManager` registra cada versão aplicada em `schema_migrations` e
nunca reaplica uma versão já registrada.

### Migration 3 — princípio aditivo

A migration 3 **não recria** nenhuma tabela das Fases 1 e 2. As tabelas
`outbox_events` e `inbox_commands` existiam desde a migration 1 como placeholders
(nenhum código escrevia nelas) e foram estendidas com `ALTER TABLE ADD COLUMN`,
preservando as colunas originais.

Consequências práticas dessa escolha:

- `outbox_events` mantém `event_type` e `payload_json` originais. O repositório da
  Fase 3 escreve `message_type` **e** `event_type` com o mesmo valor, porque
  `event_type` é `NOT NULL` sem default e não pode ser removida sem recriar a tabela.
- `message_id` foi adicionada como coluna comum e a unicidade veio por
  `CREATE UNIQUE INDEX ... WHERE message_id IS NOT NULL` — SQLite não permite
  adicionar coluna `UNIQUE` via `ALTER TABLE`.

### Garantias de unicidade relevantes

| Índice | Garante |
|---|---|
| `idx_outbox_message_id` | Deduplicação de eventos de saída |
| `idx_inbox_message_id` | Um comando repetido não vira duas linhas |
| `idx_execution_commits_attempt` | Um único commit aceito por tentativa |

Essas três são a última linha de defesa contra duplicação: mesmo que a lógica de
aplicação falhe, o banco rejeita.
