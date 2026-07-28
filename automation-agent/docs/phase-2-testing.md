# Testes — Fase 2

## Testes Unitários

### Validação
- `ManifestValidatorTests` — Manifesto válido, campos ausentes, JSON inválido, browser manifest

### Execução
- `CancellationManagerTests` — Token vinculado, cancelamento por parent, timeout, remoção
- `ResultCollectorTests` — Sucesso, falha, output JSON, artefatos, stderr, métricas

### Capacidade
- `CapacityManagerTests` — Pools, slots, incremento/decremento, interactive zero

### Segurança
- `IntegrityVerifierTests` — SHA-256 cálculo, verificação, hash incorreto

### State Machines
- `ExecutionStateMachineTests` — Transições válidas, transições inválidas, IsTerminal
- `AgentStateMachineTests` — Transições do ciclo de vida

## Testes de Integração

### Persistência
- `MigrationTests` — Todas as migrations executam, idempotência

## Cenários a Testar (checklist manual ou ponta a ponta)

| # | Cenário | Status |
|---|---------|--------|
| 1 | Manifesto background válido | ✓ |
| 2 | Manifesto com campos ausentes | ✓ |
| 3 | Download de runtime | Requer runtime real |
| 4 | Cache reutiliza runtime | Requer runtime real |
| 5 | Hash mismatch rejeitado | ✓ |
| 6 | Path traversal bloqueado | ✓ (IntegrityVerifier) |
| 7 | Archive bomb detectado | ✓ (IntegrityVerifier) |
| 8 | Capacity com máquina 4 cores | ✓ |
| 9 | Admission rejeita por memória | ✓ (AdmissionController) |
| 10 | Background Python executa | Requer runtime |
| 11 | PowerShell executa | Requer pwsh |
| 12 | Executável executa | Requer binário |
| 13 | Playwright executa | Requer runtime browser |
| 14 | Timeout funciona | ✓ (CancellationManager) |
| 15 | Cancelamento gracioso | ✓ |
| 16 | Job Object encerra árvore | Requer Windows |
| 17 | Recuperação após reinício | ✓ (ExecutionManager) |
| 18 | Cache cleanup protege em uso | ✓ (CacheManager) |

## Execução

```powershell
# Todos os testes
dotnet test AutomationAgent.sln

# Apenas unitários
dotnet test tests/Agent.UnitTests

# Apenas integração
dotnet test tests/Agent.IntegrationTests
```
