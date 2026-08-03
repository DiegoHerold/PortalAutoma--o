# Configuração

## Seções

| Seção | Descrição |
|-------|-----------|
| Agent | Nome, perfil, versão |
| Storage | Espaço mínimo em disco |
| Monitoring | Intervalo de coleta, retenção |
| MachineProfiler | Intervalo de refresh do perfil |
| Database | Timeout, journal mode |
| AgentLogging | Tamanho máximo de log, retenção |
| Execution | Timeout, cancelamento gracioso, reservas |
| Capacity | Tamanho dos pools background/browser/interactive |
| Download | Retries, timeout, limites de extração |
| Security | Verificação de hash, assinatura, path traversal |
| **Portal** | **Endpoints, registro, heartbeat, reconexão (Fase 3)** |
| Development | Diretório alternativo, console logging |

## Seção Portal

| Chave | Padrão | Descrição |
|---|---|---|
| `Enabled` | `false` | Quando false, o Agent opera só localmente |
| `ApiBaseUrl` | — | Obrigatório se habilitado; exige HTTPS |
| `WebSocketUrl` | — | Obrigatório se habilitado; exige WSS |
| `RegistrationToken` | `null` | Token de uso limitado; prefira variável de ambiente |
| `ConnectionTimeoutSeconds` | 30 | Timeout do HttpClient |
| `HeartbeatIntervalSeconds` | 15 | Deve ser menor que `ConnectionTimeoutSeconds` |
| `ReconnectInitialSeconds` | 2 | Base do backoff exponencial |
| `ReconnectMaximumSeconds` | 120 | Teto do backoff |
| `RegistrationTimeoutSeconds` | 60 | Timeout específico do registro |
| `CredentialRotationThresholdDays` | 7 | Janela em que a credencial é sinalizada para rotação |
| `RequireSecureTransport` | `true` | Só desative em teste local controlado |

O token de registro **não deve** ficar em `appsettings.json` versionado:

```powershell
$env:AUTOMATION_AGENT_Portal__RegistrationToken = "token-de-uso-limitado"
```

## Fontes (em ordem de precedência)

1. Variáveis de ambiente com prefixo `AUTOMATION_AGENT_`
2. `appsettings.{Environment}.json`
3. `appsettings.json`
4. Valores padrão no código

## Validação

Todas as opções são validadas na inicialização. Valores inválidos geram log de erro e podem impedir a inicialização.
