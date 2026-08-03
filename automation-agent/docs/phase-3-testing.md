# Testes — Fase 3

## Como executar

```powershell
# Toda a suíte
dotnet test AutomationAgent.sln

# Só unitários
dotnet test tests/Agent.UnitTests

# Só integração
dotnet test tests/Agent.IntegrationTests

# Um teste específico
dotnet test --filter "FullyQualifiedName~AgentRegistrationTests"
```

## Correções de baseline aplicadas

A inspeção inicial encontrou o repositório em estado **não compilável**. Antes de
qualquer código novo da Fase 3, três defeitos pré-existentes foram corrigidos:

| # | Arquivo | Defeito | Correção |
|---|---|---|---|
| 1 | `Agent.Domain/Identity/AgentIdentity.cs` | `sealed class` usado com expressões `with` em `AgentIdentityRepository` (CS8858 — `with` só vale para records e structs) | Convertido para `sealed record` |
| 2 | `tests/.../Persistence/MigrationTests.cs` | Chamava `new SqliteDatabaseManager(string, ILogger)`, construtor inexistente (o real recebe `IDirectoryResolver`, `IOptions<DatabaseOptions>`, `ILogger`) | Reescrito sobre `TestHelper` |
| 3 | `tests/.../Database/DatabaseMigrationTests.cs` | Variável `helper2` atribuída e nunca usada (CS0219) — vira erro por `TreatWarningsAsErrors=true` | Teste simplificado |
| 4 | `Agent.Domain/Contracts/ILauncher.cs`, `IProcessManager.cs`, e mais 7 arquivos em `Agent.Application`/`Agent.Windows` | `ExecutionContext` (tipo de domínio) colide com `System.Threading.ExecutionContext`, trazido implicitamente por `ImplicitUsings=enable` → CS0104 em toda referência não qualificada | `using ExecutionContext = Biason.AutomationAgent.Domain.Models.Execution.ExecutionContext;` em cada arquivo afetado |
| 5 | `Agent.Windows/Agent.Windows.csproj` | `WindowsDiskInfoCollector` usa `IOptions<StorageOptions>`, mas o projeto nunca referenciou `Microsoft.Extensions.Options` → CS0234/CS0246 | `<PackageReference Include="Microsoft.Extensions.Options" Version="8.0.2" />` |
| 6 | `Agent.ExecutionHost/Program.cs:52` | `pipeName ??= throw new InvalidOperationException(...)` — `throw` não é aceito como lado direito de `??=` (só de `??`, `?:` e corpo de expressão) → CS8115 | Convertido para `if (pipeName is null) throw ...` |
| 7 | `Agent.Windows/Collectors/WindowsMemoryInfoCollector.cs:48` | `Process.GetCurrentProcess()` sem qualificação — dentro da árvore de namespaces `Biason.AutomationAgent.Windows.*`, `Process` resolve para o namespace irmão `.Windows.Process` (`ProcessTreeManager`), não para `System.Diagnostics.Process` → CS0234 | Qualificado como `System.Diagnostics.Process.GetCurrentProcess()` |
| 8 | `Agent.Windows.csproj` (todo o projeto) | 35× CA1416: chamadas a `RegistryKey`, `Registry.LocalMachine`, `WindowsIdentity`/`WindowsPrincipal`, `ManagementObjectSearcher` (WMI) sinalizadas como potencialmente inseguras fora do Windows, porque o projeto builda como `net8.0` genérico apesar de ser Windows-only por desenho | `<NoWarn>$(NoWarn);CA1416</NoWarn>` no `.csproj`, com comentário explicando por que não mudamos para `net8.0-windows` (evita cascata de TFM para Agent.Application/Agent.Service/testes) |
| 9 | `Agent.Domain/Models/Execution/ExecutionAttempt.cs` | `WorkspacePath` declarado `init`-only, mas `ExecutionManager.ExecuteAsync` precisa atribuí-lo após criar o registro (o workspace só existe depois da tentativa persistida) → CS8852. Inconsistente com `ProcessId`, no mesmo arquivo, que já é `set` pelo mesmo motivo | `init` → `set` |
| 10 | `tests/.../Execution/CancellationManagerTests.cs:60` | `act.Should().NotThrow()` num `Func<Task>` — `NotThrow()` só existe para `Action` síncrona; delegate assíncrono exige `NotThrowAsync()` | Método virou `async Task`, chamada trocada para `await act.Should().NotThrowAsync()` |
| 11 | `tests/.../Security/IntegrityVerifierTests.cs` | Classe declarava `public void Dispose()` sem implementar `IDisposable` — xUnit nunca chamaria; analyzer xUnit1013 barra o build | Classe passou a implementar `IDisposable` |

O defeito #4 só apareceu ao rodar `dotnet build` de verdade (a inspeção por leitura de
código não pega ambiguidade contra tipos implícitos do BCL). Ele afeta 9 arquivos:
`ILauncher.cs`, `IProcessManager.cs`, `ProcessTreeManager.cs`, `ExecutionManager.cs`,
e os 5 launchers (`ExecutableLauncher`, `PythonModuleLauncher`, `PythonFunctionLauncher`,
`PowerShellLauncher`, `BrowserPlaywrightLauncher`). A correção usa alias de `using` em
vez de renomear o tipo — o nome `ExecutionContext` já é consumido por dezenas de pontos
no codebase e renomear seria uma mudança bem maior que o necessário.

Sem essas onze correções, nenhum teste das Fases 1 e 2 rodaria, e o critério "todos os
testes das fases anteriores devem continuar passando" seria impossível de verificar.

## Incremento 1 — Protocolo e registro

### Protocolo (`Agent.UnitTests/Protocol/EnvelopeValidatorTests.cs`)

| Teste obrigatório | Método |
|---|---|
| `protocol-version-mismatch` | `IncompatibleProtocolVersion_IsRejected` (2.0, 3.1, "abc") |
| `oversized-message` | `OversizedMessage_IsRejected` |
| `invalid-schema` | `MalformedJson_IsRejected`, `MissingMessageId_IsRejected` |

Cobertura adicional:

- `MinorVersionBump_RemainsCompatible` — 1.7 é aceito por um Agent 1.0
- `UnknownMessageType_IsRejected` — catálogo fechado
- `OutboundOnlyMessageType_FromPortal_IsRejected` — direção do fluxo
- `ExcessiveClockSkew_IsRejected` — relógio divergente
- `MessageForAnotherAgent_IsRejected` — `agent_id` incorreto
- `OutboundSerialization_RejectsOversizedPayload` — o Agent não emite acima do limite
- `OptionalFields_AreOmittedFromWire` — campos não aplicáveis são omitidos
- `MessageIds_AreUnique` — 1000 IDs sem colisão
- `CommandTypes_AreSubsetOfInbound` — invariante estrutural do catálogo

### Credenciais (`Agent.UnitTests/Credentials/CredentialProtectorTests.cs`)

| Teste obrigatório | Método |
|---|---|
| `credential-protection` | `ProtectedBlob_DoesNotContainPlaintext` |

Cobertura adicional:

- `RoundTrip_RecoversOriginalSecret`
- `SameSecret_ProducesDifferentBlobs` — nonce aleatório impede correlação
- `TamperedBlob_FailsToUnprotect` — autenticação AEAD
- `BlobFromDifferentKey_FailsToUnprotect` — cenário de VM clonada
- `TruncatedBlob_FailsGracefully`
- `AesFallback_IsNotMarkedHardened` — flag que o health check consome
- `CredentialToString_NeverRevealsSecret` — proteção contra vazamento por interpolação
- `Dpapi_RoundTrips_OnWindows` — no-op fora do Windows

### Registro (`Agent.IntegrationTests/Registration/AgentRegistrationTests.cs`)

| Teste obrigatório | Método |
|---|---|
| `agent-registration` | `Register_PersistsAgentIdAndCredential` |
| `registration-idempotent` | `SecondStartup_DoesNotRegisterAgain` |
| `invalid-registration-token` | `InvalidToken_IsRejectedWithoutPersistingAnything` |

Cobertura adicional:

- `Register_SendsIdentityFieldsToPortal`
- `RepeatedCalls_InSameProcess_RegisterOnlyOnce`
- `TransientFailure_IsMarkedRetryable` — distingue rejeição de falha de rede
- `NoRegistrationToken_ReportsNotConfigured`
- `PortalDisabled_SkipsRegistrationEntirely`
- `RevokedCredential_TriggersReRegistration`
- `ExpiredCredential_TriggersReRegistration`
- `ForceRegister_DiscardsExistingCredential`
- `IsRegistered_ReflectsPersistedState`

### Store de credenciais (`Agent.IntegrationTests/Registration/CredentialStoreTests.cs`)

| Teste obrigatório | Método |
|---|---|
| `credential-protection` | `StoredBlob_DoesNotContainPlaintextSecret`, `MetadataTable_NeverStoresSecret` |

`MetadataTable_NeverStoresSecret` varre **todas** as colunas da tabela de metadados,
não apenas as esperadas — assim, uma coluna adicionada no futuro que vazasse o
segredo quebraria o teste.

### Migrations (`Agent.IntegrationTests/Persistence/MigrationTests.cs`)

- `Phase1And2Tables_StillExist` — a migration 3 não remove nada
- `Migration3_CreatesPortalTables` — 17 tabelas novas
- `Migration3_ExtendsOutboxAdditively` / `..InboxAdditively` — colunas originais preservadas
- `Migration3_AddsPortalColumnsToExecutions`
- `InboxMessageId_IsUnique` — base de `inbox-deduplication`
- `OutboxMessageId_IsUnique` — base de `duplicated-event`
- `AcceptedCommit_IsUniquePerAttempt` — base de `duplicated-commit`
- `AllMigrations_AreRecorded` — versões 1, 2, 3
- `Initialize_IsIdempotent` — reexecução não reaplica

## Incremento 2 — WebSocket persistente e heartbeat

### Conexão (`Agent.IntegrationTests/Connection/PortalConnectionManagerTests.cs`)

| Teste obrigatório | Método |
|---|---|
| `websocket-connect` | `Connect_ReachesConnectedState_WithBearerAuthHeader` |
| `websocket-reconnect` | `ConnectionDrop_TriggersReconnect_WithFreshTransportInstance` |
| `websocket-single-connection` | `SecondRunAsyncCall_WhileFirstIsActive_ThrowsInvalidOperationException` |

Cobertura adicional:

- `Connect_WithoutRegisteredIdentity_StaysDisconnectedAndRetries` — sem `agent_id`, nem tenta abrir socket
- `HandshakeFailure_IsRetried_UntilItSucceeds` — falha no handshake não trava a máquina de estados

### Heartbeat (`Agent.IntegrationTests/Connection/HeartbeatServiceTests.cs`)

| Teste obrigatório | Método |
|---|---|
| `heartbeat` | `HeartbeatService_SendsHeartbeatPayload_OnceConnected`, `HeartbeatAck_FromPortal_UpdatesLastAckTimestamp` |

### Unitários

- `Agent.UnitTests/StateMachines/ConnectionStateMachineTests.cs` — transições válidas/inválidas, `IsOperational`, `Disabled` alcançável de qualquer estado
- `Agent.UnitTests/Connection/ConnectionBackoffCalculatorTests.cs` — teto exponencial, jitter, piso mínimo, validação de construtor

Detalhes de arquitetura e decisões de projeto: `docs/websocket.md`, `docs/heartbeat.md`.

## Testes ainda não implementados

Os incrementos 3 a 12 do brief permanecem pendentes. Os testes obrigatórios
correspondentes ainda não existem:

| Bloco | Testes pendentes |
|---|---|
| Outbox e Inbox | `outbox-persist-before-send`, `offline-spool`, `outbox-replay`, `duplicated-event`, `inbox-deduplication`, `restart-with-pending-events`, `acknowledgement`, `dead-letter` |
| Oferta e commit | `execution-offer-accept`, `execution-offer-reject`, `reservation-expiration`, `late-commit`, `duplicated-commit`, `commit-starts-preparation` |
| Lease | `lease-renewal`, `temporary-network-loss`, `lease-expiration`, `lease-recovery` |
| Session Runner | `session-runner-register`, `session-runner-authentication`, `session-runner-reconnect`, `session-detection`, `session-locked`, `session-unlocked`, `session-disconnected`, `session-logoff` |
| Interactive Pool | `interactive-exclusive`, `desktop-lock`, `session-lock`, `background-with-interactive`, `browser-with-interactive` |
| Execução desktop | `interactive-execution`, `pywinauto-execution`, `pyautogui-execution`, `excel-visible-execution`, `screenshot-on-failure`, `interactive-timeout`, `interactive-cancellation`, `session-runner-crash`, `child-process-cleanup` |
| Artefatos | `artifact-upload`, `artifact-upload-retry`, `artifact-hash`, `pending-artifact-restart`, `confirmed-artifact-cleanup` |
| Segurança | `secret-redaction`, `named-pipe-acl`, `replay-message`, `arbitrary-path-command` |

`oversized-message` e `invalid-schema` já estão cobertos pelo Incremento 1.

## Verificação — Incremento 1

Confirmado no Windows, .NET 8:

```
Construir êxito em 4,4s (9 projetos)
Resumo do teste: total: 165; falhou: 0; bem-sucedido: 165; ignorado: 0; duração: 7,5s
```

Chegar a esse resultado exigiu corrigir 11 defeitos de baseline (Fases 1 e 2), listados
acima — nenhum estava no código novo da Fase 3. A ordem em que apareceram seguiu
exatamente a cadeia de dependências do build (`Domain` → `Protocol`/`Infrastructure` →
`Windows` → `Application` → `Service`/testes), o que confirma que o repositório nunca
havia sido compilado de ponta a ponta antes desta sessão.

## Verificação — Incremento 2

**Ainda não verificado neste ambiente** (mesma limitação de sandbox do Incremento 1 —
sem `dotnet` disponível aqui). Escrito e revisado por leitura, mas só fecha "concluído"
depois de rodar `dotnet build AutomationAgent.sln && dotnet test AutomationAgent.sln`
no Windows e os 165 testes anteriores + os novos deste incremento passarem juntos.

Testes que exigem Windows de verdade e não rodam em CI Linux (fora do escopo desta
verificação, mas relevantes para os próximos incrementos):

- DPAPI (`Dpapi_RoundTrips_OnWindows` — no-op fora do Windows)
- Job Objects, WTS, Named Pipe ACL (incrementos futuros)
- pywinauto, PyAutoGUI, Excel, Domínio (incrementos futuros)
