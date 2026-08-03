# Fase 3 — Plano de Implementação (pré-código)

> Documento exigido pela seção 5 do brief da Fase 3. Escrito após inspeção completa do
> repositório (`automation-agent/`), antes de qualquer alteração de código.

## 1. Como os testes foram verificados

Não consegui executar `dotnet test` nesta sessão: o sandbox Linux do Cowork está sem VM
disponível ("VM service not running"), e mesmo se estivesse, os projetos dependem de APIs
Win32 (`user32.dll`, WTS, Job Objects, `AddWindowsService`) que só rodam de verdade no
Windows. A inspeção foi feita 100% por leitura de código-fonte.

### Resultado da inspeção: o baseline NÃO compilava

A leitura encontrou três defeitos pré-existentes que impediam o build. Isso invalida a
premissa da seção 1 do brief ("todos os testes das fases anteriores devem continuar
passando") — não havia como eles passarem.

| # | Arquivo | Defeito |
|---|---|---|
| 1 | `Agent.Domain/Identity/AgentIdentity.cs` | Declarado `sealed class`, mas `AgentIdentityRepository` usa `_cached with { ... }` em três pontos. Expressões `with` só valem para records e structs → **CS8858** |
| 2 | `tests/.../Persistence/MigrationTests.cs` | `new SqliteDatabaseManager(_dbPath, logger)` — esse construtor não existe; o real recebe `IDirectoryResolver`, `IOptions<DatabaseOptions>`, `ILogger` |
| 3 | `tests/.../Database/DatabaseMigrationTests.cs` | `var helper2 = new TestHelper();` nunca usado → **CS0219**, que vira erro por `TreatWarningsAsErrors=true` |

Os três foram corrigidos com a menor alteração possível antes de qualquer código novo:
`AgentIdentity` virou `record`, `MigrationTests` foi reescrito sobre `TestHelper`, e o
teste de idempotência foi simplificado.

**Ação pendente do seu lado:** rodar `automation-agent/scripts/run-tests.ps1` no Windows
para confirmar que o baseline agora fecha verde.

## 2. Arquitetura atual (Fases 1 e 2)

```
Agent.Service (Worker Service host, DI, appsettings, Windows Service)
    └─ AgentWorker (BackgroundService): boot → identity → profile → capabilities →
       recover orphaned → health checks → Ready/Degraded
Agent.Application (casos de uso)
    ├─ Services: MachineProfilerService, MachineReportGenerator
    ├─ Capacity: CapacityManager, ResourceReservationManager, AdmissionController
    ├─ Execution: WorkspaceManager, CancellationManager, ExecutionManager,
    │             ResultCollector, CacheManager, ExecutionMetricsCollector
    ├─ Launchers: PythonFunction/PythonModule/PowerShell/Executable/BrowserPlaywright
    ├─ Validation: ManifestValidator
    ├─ HealthChecks: HealthCheckRunner
    └─ Diagnostics: DiagnosticsExporter
Agent.Domain (sem dependências externas)
    ├─ Enums: AgentState, ExecutionState, PoolType, RuntimeType, EntrypointType,
    │         DownloadStatus, ArtifactStatus, ReservationStatus, SessionType/Status,
    │         CapabilityStatus, HealthStatus
    ├─ StateMachines: AgentStateMachine, ExecutionStateMachine
    ├─ Identity: AgentIdentity (installation_id, agent_id?, machine_id, instance_id)
    ├─ Models: manifest, capacity, execution, storage, session, capability, health
    └─ Contracts: ~25 interfaces (repositórios, coletores, managers)
Agent.Infrastructure
    ├─ Database: SqliteDatabaseManager + Migrations (2 migrations aplicadas)
    ├─ Persistence: 10 repositórios (identity, state, execução, capacidade, artefatos...)
    ├─ Security: IntegrityVerifier (SHA-256, path traversal, zip bomb)
    ├─ Downloads: DownloadManager (retry, backoff exponencial, streaming, verificação)
    └─ Stores: RuntimeStore, PackageStore (imutáveis, versionados)
Agent.Windows
    ├─ Collectors: OS, CPU (info + uso), memória, disco, sessão (WTS básico)
    ├─ Detection: WindowsSoftwareDetector, WindowsCapabilityDetector
    └─ Process: JobObjectManager, ProcessTreeManager (+ interop nativo)
Agent.Protocol
    └─ ProtocolEnvelope (protocol_version, message_id, correlation_id, causation_id,
       message_type, sent_at, agent_id, agent_instance_id, payload) + MachineReport
Agent.ExecutionHost (executável separado, já publicado sozinho)
    └─ Protocol: HostMessage + PipeClient (Named Pipe JSON-lines, sequence monotônica,
       message_type, execution_id, execution_attempt_id) — comunica com Agent.Service
```

Nenhum componente de Portal, WebSocket, Session Runner ou execução interativa existe hoje
(`grep` por `WebSocket|SignalR|Portal` no `src/` só encontra um comentário em
`Agent.ExecutionHost/Program.cs`).

## 3. Componentes reutilizáveis (não recriar)

| Necessidade da Fase 3 | Já existe como | Ação |
|---|---|---|
| Envelope de protocolo Portal↔Agent | `Agent.Protocol.ProtocolEnvelope` | Estender (adicionar `installation_id`, `execution_id`, `execution_attempt_id`, `sequence` opcionais) — não recriar |
| Protocolo local autenticado (Named Pipe) | `Agent.ExecutionHost.Protocol.HostMessage` + `PipeClient` (JSON-lines, sequence, execution_id/attempt_id) | Usar o mesmo formato de envelope para o pipe Agent.Service↔SessionRunner; extrair para `Agent.Protocol` se fizer sentido compartilhar |
| Outbox/Inbox (tabelas) | `outbox_events`, `inbox_commands` (migration 1) — schema mínimo (`event_type`, `payload_json`, `retry_count`) | **Evoluir via migration 3**, não recriar: faltam `message_id` (dedupe), `execution_id`, `execution_attempt_id`, `sequence`, `status` rico (`pending/sending/sent/acknowledged/dead_letter`), `acknowledged_at` |
| Máquina de estados do Agent | `AgentStateMachine` (já tem `Draining`, `Degraded`, `Ready` etc.) | Reusar sem alteração — `connection_state` do WebSocket é um conceito **separado**, não deve virar novo estado do Agent |
| Máquina de estados de execução | `ExecutionStateMachine` (já tem `Offered→Reserved→Committed→Preparing→Starting→Running→...→Cancelled/Failed/Interrupted/Orphaned`) | Já cobre 100% do fluxo de oferta/commit/lease da Fase 3. Não criar segunda state machine |
| Identidade / registro | `AgentIdentity.AgentId` (nullable) + `RegisteredAtUtc` (nullable) + `IAgentIdentityService.UpdateAgentIdAsync` | Já preparado para registro no Portal — só falta o fluxo HTTP e persistência de credencial |
| Pool interativo | `PoolType.Interactive`, `CapacityOptions.InteractivePoolSize = 1` (default já é 1) | Reusar CapacityManager/AdmissionController tal como estão — só adicionar validações específicas (sessão, lock de desktop) na avaliação de admissão |
| Download com retomada/hash/retry | `DownloadManager` + `IntegrityVerifier` | Reusar padrão (HttpClient, backoff exponencial) para construir o **upload** de artefatos (fluxo inverso) |
| Isolamento de processo | `JobObjectManager`, `ProcessTreeManager` | Reusar para o Execution Host lançado pelo Session Runner |
| Execution pipeline | `ExecutionManager.ExecuteAsync` (Preparing→Starting→Running→Succeeded/Failed, recuperação de órfãos) | Não recriar; a execução interativa é um **modo** dentro do mesmo pipeline, não um segundo pipeline |
| Capability model | `Capability` (key/status/version/source) + `WindowsCapabilityDetector` | Reusar para `dominio.installed`, `office.excel` |
| Manifesto | `AutomationManifest` (schema_version, runtime, entrypoint, capabilities, resources, timeout) | Estender com `execution.mode`, `session_policy`, `exclusive_resources` — mesmo objeto, não um segundo formato |

## 4. Lacunas (o que a Fase 3 precisa criar)

- Nenhum cliente HTTP/WebSocket para o Portal (registro, conexão persistente, heartbeat).
- Nenhum armazenamento protegido de credencial (DPAPI) — `AgentIdentity` guarda só o `agent_id`, não um token.
- Outbox/Inbox atuais não suportam ACK, dedupe por `message_id`, dead-letter, nem vínculo a `execution_attempt_id`/`sequence`.
- Nenhuma oferta/lease de execução vinda de fora — hoje toda execução nasce localmente (CLI/testes), não existe `execution.offer`→`accept`→`commit`.
- `Agent.SessionRunner` (projeto novo) não existe.
- Nenhum Named Pipe autenticado por ACL/token — o pipe atual (ExecutionHost↔Service) é local, sem autenticação de sessão nem ACL restrita a validar aqui.
- Detecção de sessão é single-session e roda no processo atual (`Process.GetCurrentProcess().SessionId`), inadequada para o Agent Service rodando como Windows Service na Sessão 0 — precisa de enumeração WTS real (`WTSEnumerateSessions`) a partir do serviço.
- Sem locks de recurso exclusivo (`windows_desktop`, `dominio_application`, `excel_application`).
- Sem PyAutoGUI/pywinauto no runtime empacotado nem launcher desktop dedicado.
- Sem upload HTTPS de artefatos.
- Sem Portal Simulator.
- Sem CLI de desenvolvimento (`portal status`, `outbox retry` etc.) — hoje só existem os comandos ad hoc no `AgentWorker` (`profile`, `diagnostics`, `cache status/cleanup`, `execution list`).

## 5. Riscos

1. **Outbox/Inbox migration é a peça mais arriscada** — evoluir tabelas já em produção (Fase 1/2) sem quebrar `ExecutionEventRepository`/quem já grava nelas. Migration 3 precisa ser aditiva (novas colunas nullable + backfill), não um `DROP TABLE`.
2. **Sessão 0 isolation** é real: o `Agent.Service` (Windows Service) fisicamente não enxerga o desktop do usuário. Todo desenho do Session Runner depende disso estar certo desde o primeiro incremento, senão a Fase 3 inteira desmorona.
3. Sem ambiente Windows real neste sandbox, não consigo validar em runtime: Named Pipe ACL, Job Objects, WTS, DPAPI, PyAutoGUI/pywinauto. Vou escrever o código e os testes que puderem rodar em CI comum; a validação end-to-end em máquina Windows real fica sob sua responsabilidade (ou de um agente com acesso Windows).
4. Escopo é enorme (12 incrementos, ~26 componentes novos, 8 projetos). Fazer tudo em uma tacada só aumenta a chance de "código parcialmente conectado", que a própria Fase 3 proíbe.

## 6. Contratos que serão alterados

- `ProtocolEnvelope` (Agent.Protocol) — novos campos opcionais.
- `AutomationManifest` / `ManifestResources` — `mode`, `session_policy`, `exclusive_resources`.
- `IAgentIdentityService` — adicionar persistência de credencial protegida (novo método, não quebra o existente).
- Migration 3: `outbox_events` e `inbox_commands` ganham colunas; novas tabelas listadas na seção 46 do brief.

## 7. Migrations necessárias (migration 3, aditiva)

`agent_registration`, `agent_credentials_metadata`, `portal_connections`, `connection_events`,
colunas novas em `inbox_commands`/`outbox_events`, `message_acknowledgements`,
`execution_offers`, `execution_commits`, `execution_leases`, `session_runners`,
`interactive_sessions`, `session_events`, `pending_artifacts`, `artifact_upload_attempts`,
`protocol_errors`, `sync_runs`.

## 8. Plano incremental proposto

Segue a ordem da seção 54 do brief, mapeada ao que já existe:

| # | Incremento | Reaproveita | Cria |
|---|---|---|---|
| 1 | Protocolo + registro | `ProtocolEnvelope`, `AgentIdentity` | DPAPI credential store, `AgentRegistrationService`, HTTP client ao Portal |
| 2 | WebSocket + heartbeat | `AgentStateMachine` (para estado geral) | `PortalConnectionManager`, `ConnectionState`, `HeartbeatService` |
| 3 | Outbox/Inbox | Tabelas migration 1 (evoluídas) | Migration 3, `BatchSender`, `AcknowledgementManager`, dedupe |
| 4 | Oferta/reserva/commit | `ExecutionStateMachine`, `AdmissionController`, `ResourceReservationManager` | `ExecutionOfferHandler`, expiração de reserva |
| 5 | Leases | `ExecutionManager` (execução já roda) | `ExecutionLeaseManager`, renovação, reconciliação |
| 6 | Artefatos HTTPS | `IntegrityVerifier`, padrão do `DownloadManager` | `ArtifactUploadManager` |
| 7 | Session Runner | `Agent.ExecutionHost` como referência de projeto standalone | `Agent.SessionRunner`, `SessionRunner.exe` |
| 8 | Named Pipe autenticado | `HostMessage`/`PipeClient` como base de protocolo | ACL, token de sessão/execução |
| 9 | Interactive Pool | `PoolType.Interactive`, `CapacityOptions.InteractivePoolSize` | Locks de desktop, admissão interativa |
| 10 | Execution Host interativo | `ExecutionManager`, `JobObjectManager`, launchers existentes | Launcher desktop (pywinauto/PyAutoGUI), screenshots |
| 11 | Excel/Domínio | `Capability`, `WindowsCapabilityDetector` | Policies de processo existente, locks `excel_application`/`dominio_application` |
| 12 | Recuperação + docs + simulador | `docs/` (padrão já estabelecido) | Portal Simulator, docs novos, testes ponta a ponta |

Cada incremento termina com testes rodando (ou pelo menos compilando + testes unitários que
não dependem de Windows real) antes de avançar para o próximo — conforme exigido pela seção 54.

## 9. Estado de execução

| Incremento | Estado |
|---|---|
| 0 — Correção do baseline | **concluído e verificado** (11 defeitos de compilação corrigidos) |
| 1 — Protocolo e registro | **concluído e verificado** — `dotnet build` limpo, 165/165 testes passando |
| 2 — WebSocket e heartbeat | **concluído e verificado** — `dotnet build` limpo, 203/203 testes passando |
| 3 — Outbox e Inbox persistentes | **concluído e verificado** — `dotnet build` limpo, 210/210 testes passando |
| 4 a 12 | pendentes |

Verificado em: `dotnet build AutomationAgent.sln` (êxito, 9 projetos) e
`dotnet test AutomationAgent.sln` (210 testes, 0 falhas), rodado no Windows.

O total de 11 defeitos de baseline (não 3, como estimado na inspeção inicial) só
apareceu ao rodar o compilador de verdade — a leitura de código não pega ambiguidade
de namespace, CA1416 ou uso incorreto de API de teste. Lista completa em
`docs/phase-3-testing.md`.

### O que o Incremento 1 entregou

**Criados**

```
src/Agent.Protocol/Envelope/ProtocolConstants.cs
src/Agent.Protocol/Messages/PortalMessageTypes.cs
src/Agent.Protocol/Serialization/ProtocolJson.cs
src/Agent.Protocol/Validation/EnvelopeValidator.cs
src/Agent.Protocol/Validation/EnvelopeValidationResult.cs
src/Agent.Protocol/Registration/RegistrationContracts.cs
src/Agent.Domain/Agents/AgentCredential.cs
src/Agent.Domain/Agents/RegistrationResult.cs
src/Agent.Domain/Configuration/PortalOptions.cs
src/Agent.Domain/Contracts/ICredentialProtector.cs
src/Agent.Domain/Contracts/IAgentCredentialStore.cs
src/Agent.Domain/Contracts/IAgentRegistrationService.cs
src/Agent.Domain/Contracts/IPortalApiClient.cs
src/Agent.Infrastructure/Credentials/DpapiCredentialProtector.cs
src/Agent.Infrastructure/Credentials/AesFileKeyCredentialProtector.cs
src/Agent.Infrastructure/Credentials/CredentialProtectorFactory.cs
src/Agent.Infrastructure/Credentials/AgentCredentialStore.cs
src/Agent.Infrastructure/Http/PortalApiClient.cs
src/Agent.Application/Registration/AgentRegistrationService.cs
tests/Agent.UnitTests/Protocol/EnvelopeValidatorTests.cs
tests/Agent.UnitTests/Credentials/CredentialProtectorTests.cs
tests/Agent.IntegrationTests/Registration/AgentRegistrationTests.cs
tests/Agent.IntegrationTests/Registration/CredentialStoreTests.cs
docs/protocol.md
docs/agent-registration.md
docs/phase-3-testing.md
```

**Alterados**

```
src/Agent.Domain/Identity/AgentIdentity.cs        class → record (+ IsRegistered)
src/Agent.Protocol/Envelope/ProtocolEnvelope.cs   novos campos opcionais
src/Agent.Infrastructure/Database/Migrations.cs   migration 3
src/Agent.Infrastructure/Agent.Infrastructure.csproj  + Protocol, DPAPI, Http.Json
src/Agent.Application/HealthChecks/HealthCheckRunner.cs  + agent_registration
src/Agent.Application/Diagnostics/DiagnosticsExporter.cs + registration-status.json
src/Agent.Service/Program.cs                      DI da Fase 3
src/Agent.Service/AgentWorker.cs                  registro no boot + portal status/register
src/Agent.Service/appsettings.json                seção Portal, versão 0.3.0
src/Agent.Service/appsettings.Development.json    Portal local
tests/Agent.IntegrationTests/Helpers/TestHelper.cs  fábricas de credencial
tests/Agent.IntegrationTests/Persistence/MigrationTests.cs  reescrito
tests/Agent.IntegrationTests/Database/DatabaseMigrationTests.cs  correção CS0219
docs/database.md, docs/configuration.md
```

### Decisões de projeto que valem registro

1. **`IPortalApiClient` usa tipos de domínio, não DTOs de wire.** A primeira versão
   importava `Agent.Protocol.Registration` dentro de `Agent.Domain`, o que criaria
   dependência circular (Protocol → Domain já existe). O contrato ficou livre de wire e
   o mapeamento vive em `PortalApiClient`.

2. **Credencial gravada antes do `agent_id`.** Se o processo morrer no meio, sobra
   credencial órfã e a próxima inicialização registra de novo. A ordem inversa deixaria
   `agent_id` sem credencial utilizável — o Agent se acharia registrado sem conseguir
   autenticar.

3. **"Registrado" exige que o blob realmente desproteja.** Não basta ter `agent_id` e
   metadados: o serviço tenta desproteger de fato. Isso cobre VM clonada e perfil DPAPI
   recriado, onde o `agent_id` sobrevive mas a credencial não abre.

4. **Migration 3 é estritamente aditiva.** `outbox_events` e `inbox_commands` eram
   placeholders da migration 1 sem nenhum código escrevendo neles, mas foram estendidos
   com `ALTER TABLE` em vez de recriados, preservando `event_type`/`payload_json` e o
   teste que verifica a existência dessas tabelas.

5. **Unicidade delegada ao banco.** `idx_outbox_message_id`, `idx_inbox_message_id` e
   `idx_execution_commits_attempt` são a última linha de defesa contra duplicação: mesmo
   com falha na lógica de aplicação, o SQLite rejeita.

### Verificação

Confirmado no Windows: `dotnet build AutomationAgent.sln` fecha limpo (9 projetos) e
`dotnet test AutomationAgent.sln` passa 165/165, incluindo os ~45 testes novos desta
fase (protocolo, credenciais, registro, migration 3) e todos os testes das Fases 1 e 2.

## 10. O que o Incremento 2 entregou

**Criados**

```
src/Agent.Domain/Enums/ConnectionState.cs
src/Agent.Domain/StateMachines/ConnectionStateMachine.cs
src/Agent.Domain/Models/Connections/ConnectionStatus.cs
src/Agent.Domain/Contracts/IWebSocketTransport.cs
src/Agent.Domain/Contracts/IPortalConnectionManager.cs
src/Agent.Domain/Contracts/IConnectionStateRepository.cs
src/Agent.Protocol/Messages/HeartbeatPayload.cs
src/Agent.Application/Heartbeat/HeartbeatSnapshotBuilder.cs
src/Agent.Application/Heartbeat/HeartbeatService.cs
src/Agent.Application/Connection/ConnectionBackoffCalculator.cs
src/Agent.Application/Connection/PortalConnectionManager.cs
src/Agent.Application/Connection/PortalConnectionHostedService.cs
src/Agent.Infrastructure/WebSockets/ClientWebSocketTransport.cs
src/Agent.Infrastructure/Persistence/PortalConnectionRepository.cs
tests/Agent.IntegrationTests/Helpers/FakeWebSocketTransport.cs
tests/Agent.IntegrationTests/Connection/PortalConnectionManagerTests.cs
tests/Agent.IntegrationTests/Connection/HeartbeatServiceTests.cs
tests/Agent.UnitTests/StateMachines/ConnectionStateMachineTests.cs
tests/Agent.UnitTests/Connection/ConnectionBackoffCalculatorTests.cs
docs/websocket.md
docs/heartbeat.md
```

**Alterados**

```
src/Agent.Application/HealthChecks/HealthCheckRunner.cs   + websocket, + heartbeat
src/Agent.Service/Program.cs                              DI do Incremento 2
src/Agent.Service/AgentWorker.cs                           portal status (+connection),
                                                             portal connection-events
tests/Agent.IntegrationTests/Helpers/TestHelper.cs         CreateConnectionRepository,
                                                             SeedRegisteredAgentAsync
docs/phase-3-testing.md                                    tabela do Incremento 2
```

### Decisões de projeto que valem registro

1. **`Disconnected → Reconnecting` é proibido de propósito.** A primeira versão do
   `MainLoopAsync` tentava essa transição sempre que uma conexão falhava, inclusive na
   primeira tentativa (antes do registro terminar) — o que a máquina de estados rejeita
   silenciosamente (só um log em Debug), deixando `GetStatus()` reportar um estado
   defasado. Corrigido movendo toda decisão de transição para dentro de
   `TryConnectAndPumpAsync`/`HandleDisconnectAsync`: o loop principal só decide *quando*
   tentar de novo (backoff), nunca *para qual* estado ir.

2. **`TrySendAsync` descarta em vez de reter.** Cheguei a documentar o oposto na
   primeira versão do contrato (`IPortalConnectionManager`) — dizia que a mensagem
   "aguarda na fila" quando a conexão cai. A implementação real sempre descartou
   (retorna `false` e quem chamou decide o que fazer). Corrigi o comentário para bater
   com o código: reter e reenviar é trabalho do Outbox (Incremento 3), não desta classe.

3. **Cada tentativa de reconexão usa um transporte novo.** Tanto
   `ClientWebSocketTransportFactory` quanto `FakeWebSocketTransportFactory` (teste)
   criam uma instância por chamada — nunca reaproveitam um socket que já caiu. Isso é
   verificado por teste (`ConnectionDrop_TriggersReconnect_WithFreshTransportInstance`
   compara identidade de objeto, não só contagem).

4. **`Degraded` existe na máquina de estados mas não é usado pelo
   `PortalConnectionManager` ainda.** É reservado para "socket de pé, Portal não
   responde" — que hoje só o health check de heartbeat detecta (via ausência de ack),
   sem forçar a conexão em si a mudar de estado. Evita adicionar uma segunda forma de
   "meio conectado" que teria que ser reconciliada com o watchdog de silêncio.

5. **CLI não controla um Agent já em execução.** Cheguei a planejar `portal
   connect`/`portal disconnect` como comandos de controle, mas cada invocação de CLI é
   um processo novo — não haveria como afetar o `PortalConnectionManager` do serviço
   Windows já rodando sem um canal de IPC que não existe ainda. Implementei em vez
   disso `portal status` estendido (bloco `connection`) e `portal connection-events`,
   que são diagnóstico honesto do que já é possível hoje.

### Verificação

Confirmado no Windows, .NET 8:

```
Construir êxito em 13,0s (9 projetos)
Resumo do teste: total: 203; falhou: 0; bem-sucedido: 203; ignorado: 0; duração: 7,3s
```

Um defeito surgiu na primeira rodada e foi corrigido antes desta confirmação: o campo
`PortalConnectionManager._running` era escrito mas nunca lido (CS0414, erro por
`TreatWarningsAsErrors=true`) — sobra de um rascunho anterior que guardava o estado de
execução sem expô-lo. Corrigido expondo `public bool IsRunning => _running;`, que é
diagnóstico legítimo (mesmo padrão de `CurrentState`) em vez de apenas suprimir o aviso.

203 testes = 165 das Fases 1/2 e do Incremento 1 + 38 novos deste incremento (conexão,
heartbeat, máquina de estados de conexão, backoff).

## 11. O que o Incremento 3 entregou

**Criados**

```
src/Agent.Domain/Configuration/MessagingOptions.cs
src/Agent.Domain/Models/Messaging/OutboxMessage.cs
src/Agent.Domain/Models/Messaging/InboxCommand.cs
src/Agent.Domain/Models/Messaging/MessagingDiagnostics.cs
src/Agent.Domain/Models/Messaging/MessageAcknowledgement.cs
src/Agent.Domain/Contracts/IOutboxRepository.cs
src/Agent.Domain/Contracts/IInboxRepository.cs
src/Agent.Domain/Contracts/IMessageAcknowledgementRepository.cs
src/Agent.Protocol/Messages/AcknowledgementPayloads.cs
src/Agent.Infrastructure/Persistence/OutboxRepository.cs
src/Agent.Infrastructure/Persistence/InboxRepository.cs
src/Agent.Infrastructure/Persistence/MessageAcknowledgementRepository.cs
src/Agent.Application/Messaging/OutboxMessagePublisher.cs
src/Agent.Application/Messaging/OutboxBatchSender.cs
src/Agent.Application/Messaging/PortalMessageAcknowledgementService.cs
src/Agent.Application/Messaging/PortalInboxService.cs
src/Agent.Application/Messaging/InboxCommandProcessor.cs
src/Agent.Application/Messaging/InboxCommandHandler.cs
tests/Agent.IntegrationTests/Messaging/OutboxInboxTests.cs
docs/outbox-inbox.md
```

**Alterados**

```
src/Agent.Application/Connection/PortalConnectionManager.cs  envio serializado durável
src/Agent.Domain/Contracts/IPortalConnectionManager.cs       TrySendSerializedAsync
src/Agent.Application/Heartbeat/HeartbeatService.cs          outbox_pending real
src/Agent.Application/HealthChecks/HealthCheckRunner.cs      durable_messaging
src/Agent.Application/Diagnostics/DiagnosticsExporter.cs     messaging-diagnostics.json
src/Agent.Service/Program.cs                                 DI do Incremento 3
src/Agent.Service/AgentWorker.cs                             portal messaging/status
src/Agent.Service/appsettings.json                           seção Messaging
tests/Agent.IntegrationTests/Helpers/TestHelper.cs           fábricas dos repositórios
docs/database.md, docs/configuration.md, docs/heartbeat.md
```

### Decisões de projeto que valem registro

1. **O contrato de conexão não depende de `ProtocolEnvelope`.** `Agent.Protocol` já
   referencia `Agent.Domain`; colocar o envelope no contrato do domínio criaria ciclo.
   A fronteira ficou como `TrySendSerializedAsync`: a aplicação monta e valida o envelope,
   e o connection manager só enfileira o JSON já validado.

2. **`command.ack` também passa pelo Outbox.** ACK de comando é uma mensagem importante
   de saída, então não usa envio best-effort direto. Ele é persistido, enviado e
   confirmado como qualquer outra mensagem Agent -> Portal.

3. **Comando sem handler permanece pendente.** O Incremento 4 ainda vai implementar
   oferta/reserva/commit. Para não mascarar integração ausente, o dispatcher só processa
   comandos com `IInboxCommandHandler` registrado; os demais ficam na Inbox para replay
   futuro em vez de fingirem sucesso.

4. **Ordenação é conservadora por tentativa.** Uma mensagem com sequence maior para o
   mesmo `execution_attempt_id` não é enviada enquanto existir sequence anterior não
   `acknowledged`/`dead_letter`. É menos agressivo que pipelining, mas evita confirmar
   fora de ordem nesta fase.

### Verificação

Confirmado no Windows, .NET 8:

```
Compilação com êxito (9 projetos, 0 warnings)
Resumo do teste: total: 210; falhou: 0; bem-sucedido: 210; ignorado: 0
```

Os 7 testes novos cobrem `outbox-persist-before-send`, `offline-spool`,
`outbox-replay`, `duplicated-event`, `inbox-deduplication`, `acknowledgement`,
`dead-letter` e recuperação de pendências após reinício pelo mesmo mecanismo de replay.
