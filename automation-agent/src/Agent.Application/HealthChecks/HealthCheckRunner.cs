using Biason.AutomationAgent.Application.Heartbeat;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models;
using Biason.AutomationAgent.Domain.StateMachines;
using Microsoft.Extensions.Logging;

namespace Biason.AutomationAgent.Application.HealthChecks;

public sealed class HealthCheckRunner
{
    private readonly IDatabaseManager _dbManager;
    private readonly IDirectoryResolver _dirs;
    private readonly IClock _clock;
    private readonly ICacheManager? _cacheManager;
    private readonly ICapacityManager? _capacityManager;
    private readonly IAgentCredentialStore? _credentialStore;
    private readonly ICredentialProtector? _credentialProtector;
    private readonly Domain.Configuration.PortalOptions? _portalOptions;
    private readonly IPortalConnectionManager? _connectionManager;
    private readonly HeartbeatService? _heartbeatService;
    private readonly ILogger<HealthCheckRunner> _logger;

    public HealthCheckRunner(
        IDatabaseManager dbManager,
        IDirectoryResolver dirs,
        IClock clock,
        ILogger<HealthCheckRunner> logger,
        ICacheManager? cacheManager = null,
        ICapacityManager? capacityManager = null,
        IAgentCredentialStore? credentialStore = null,
        ICredentialProtector? credentialProtector = null,
        Microsoft.Extensions.Options.IOptions<Domain.Configuration.PortalOptions>? portalOptions = null,
        IPortalConnectionManager? connectionManager = null,
        HeartbeatService? heartbeatService = null)
    {
        _dbManager = dbManager;
        _dirs = dirs;
        _clock = clock;
        _cacheManager = cacheManager;
        _capacityManager = capacityManager;
        _credentialStore = credentialStore;
        _credentialProtector = credentialProtector;
        _portalOptions = portalOptions?.Value;
        _connectionManager = connectionManager;
        _heartbeatService = heartbeatService;
        _logger = logger;
    }

    public async Task<IReadOnlyList<HealthCheckResult>> RunAllAsync(CancellationToken ct = default)
    {
        var results = new List<HealthCheckResult>
        {
            CheckProcess(),
            await CheckDatabaseAsync(ct),
            CheckStorage(),
            CheckConfiguration(),
            CheckRuntimeStore(),
            CheckPackageStore(),
            CheckCapacityManager(),
            CheckExecutionHostAvailability(),
            await CheckAgentRegistrationAsync(ct),
            CheckWebSocketConnection(),
            CheckHeartbeat()
        };

        foreach (var r in results)
        {
            if (r.Status != HealthStatus.Healthy)
                _logger.LogWarning("Health check {Component}: {Status} - {Message}", r.Component, r.Status, r.Message);
        }

        return results;
    }

    public HealthStatus GetOverallStatus(IReadOnlyList<HealthCheckResult> results)
    {
        if (results.Any(r => r.Status == HealthStatus.Unhealthy))
            return HealthStatus.Unhealthy;
        if (results.Any(r => r.Status == HealthStatus.Degraded))
            return HealthStatus.Degraded;
        return HealthStatus.Healthy;
    }

    private HealthCheckResult CheckProcess()
    {
        return new HealthCheckResult
        {
            Component = "process",
            Status = HealthStatus.Healthy,
            Message = "Process is running",
            CheckedAtUtc = _clock.UtcNow
        };
    }

    private async Task<HealthCheckResult> CheckDatabaseAsync(CancellationToken ct)
    {
        try
        {
            var ok = await _dbManager.VerifyIntegrityAsync(ct);
            return new HealthCheckResult
            {
                Component = "database",
                Status = ok ? HealthStatus.Healthy : HealthStatus.Unhealthy,
                Message = ok ? "Database integrity OK" : "Database integrity check failed",
                CheckedAtUtc = _clock.UtcNow
            };
        }
        catch (Exception ex)
        {
            return new HealthCheckResult
            {
                Component = "database",
                Status = HealthStatus.Unhealthy,
                Message = $"Database check error: {ex.Message}",
                CheckedAtUtc = _clock.UtcNow
            };
        }
    }

    private HealthCheckResult CheckStorage()
    {
        try
        {
            var root = Path.GetPathRoot(_dirs.RootPath) ?? "C:\\";
            var drive = new DriveInfo(root);
            var freeMb = drive.AvailableFreeSpace / (1024 * 1024);

            if (freeMb < 512)
            {
                return new HealthCheckResult
                {
                    Component = "storage",
                    Status = HealthStatus.Unhealthy,
                    Message = $"Critical disk space: {freeMb}MB free",
                    CheckedAtUtc = _clock.UtcNow
                };
            }

            if (freeMb < 2048)
            {
                return new HealthCheckResult
                {
                    Component = "storage",
                    Status = HealthStatus.Degraded,
                    Message = $"Low disk space: {freeMb}MB free",
                    CheckedAtUtc = _clock.UtcNow
                };
            }

            return new HealthCheckResult
            {
                Component = "storage",
                Status = HealthStatus.Healthy,
                Message = $"Disk space OK: {freeMb}MB free",
                CheckedAtUtc = _clock.UtcNow
            };
        }
        catch (Exception ex)
        {
            return new HealthCheckResult
            {
                Component = "storage",
                Status = HealthStatus.Degraded,
                Message = $"Storage check error: {ex.Message}",
                CheckedAtUtc = _clock.UtcNow
            };
        }
    }

    private HealthCheckResult CheckConfiguration()
    {
        var valid = _dirs.Validate(out var errors);
        return new HealthCheckResult
        {
            Component = "configuration",
            Status = valid ? HealthStatus.Healthy : HealthStatus.Degraded,
            Message = valid ? "Configuration OK" : $"Configuration issues: {string.Join("; ", errors)}",
            CheckedAtUtc = _clock.UtcNow
        };
    }

    private HealthCheckResult CheckRuntimeStore()
    {
        try
        {
            var path = _dirs.RuntimesPath;
            var exists = Directory.Exists(path);
            return new HealthCheckResult
            {
                Component = "runtime_store",
                Status = exists ? HealthStatus.Healthy : HealthStatus.Degraded,
                Message = exists ? "Runtime store directory exists" : "Runtime store directory missing",
                CheckedAtUtc = _clock.UtcNow
            };
        }
        catch (Exception ex)
        {
            return new HealthCheckResult
            {
                Component = "runtime_store",
                Status = HealthStatus.Degraded,
                Message = $"Runtime store check error: {ex.Message}",
                CheckedAtUtc = _clock.UtcNow
            };
        }
    }

    private HealthCheckResult CheckPackageStore()
    {
        try
        {
            var path = _dirs.PackagesPath;
            var exists = Directory.Exists(path);
            return new HealthCheckResult
            {
                Component = "package_store",
                Status = exists ? HealthStatus.Healthy : HealthStatus.Degraded,
                Message = exists ? "Package store directory exists" : "Package store directory missing",
                CheckedAtUtc = _clock.UtcNow
            };
        }
        catch (Exception ex)
        {
            return new HealthCheckResult
            {
                Component = "package_store",
                Status = HealthStatus.Degraded,
                Message = $"Package store check error: {ex.Message}",
                CheckedAtUtc = _clock.UtcNow
            };
        }
    }

    private HealthCheckResult CheckCapacityManager()
    {
        if (_capacityManager is null)
        {
            return new HealthCheckResult
            {
                Component = "capacity_manager",
                Status = HealthStatus.Degraded,
                Message = "Capacity manager not available",
                CheckedAtUtc = _clock.UtcNow
            };
        }

        try
        {
            var snapshot = _capacityManager.GetSnapshot();
            var totalAvailable = snapshot.Pools.Values.Sum(p => p.Available);
            return new HealthCheckResult
            {
                Component = "capacity_manager",
                Status = totalAvailable > 0 ? HealthStatus.Healthy : HealthStatus.Degraded,
                Message = $"Capacity: {totalAvailable} slots available across {snapshot.Pools.Count} pools",
                CheckedAtUtc = _clock.UtcNow
            };
        }
        catch (Exception ex)
        {
            return new HealthCheckResult
            {
                Component = "capacity_manager",
                Status = HealthStatus.Degraded,
                Message = $"Capacity check error: {ex.Message}",
                CheckedAtUtc = _clock.UtcNow
            };
        }
    }

    /// <summary>
    /// Estado do registro do Agent junto ao Portal.
    ///
    /// Regras (seção 47): credencial revogada é <c>unhealthy</c> para comunicação;
    /// ausência de registro com Portal habilitado é <c>degraded</c> — o Agent segue
    /// funcional localmente. Nenhum valor de credencial é exposto na mensagem.
    /// </summary>
    private async Task<HealthCheckResult> CheckAgentRegistrationAsync(CancellationToken ct)
    {
        const string component = "agent_registration";

        if (_portalOptions is null || !_portalOptions.Enabled)
        {
            return new HealthCheckResult
            {
                Component = component,
                Status = HealthStatus.Healthy,
                Message = "Integração com o Portal desabilitada",
                CheckedAtUtc = _clock.UtcNow
            };
        }

        if (_credentialStore is null)
        {
            return new HealthCheckResult
            {
                Component = component,
                Status = HealthStatus.Degraded,
                Message = "Credential store indisponível",
                CheckedAtUtc = _clock.UtcNow
            };
        }

        try
        {
            var metadata = await _credentialStore.GetMetadataAsync(ct);

            if (metadata is null)
            {
                return new HealthCheckResult
                {
                    Component = component,
                    Status = HealthStatus.Degraded,
                    Message = "Agent ainda não registrado no Portal",
                    CheckedAtUtc = _clock.UtcNow
                };
            }

            if (metadata.IsRevoked)
            {
                return new HealthCheckResult
                {
                    Component = component,
                    Status = HealthStatus.Unhealthy,
                    Message = "Credencial revogada; comunicação com o Portal indisponível",
                    CheckedAtUtc = _clock.UtcNow
                };
            }

            if (metadata.ExpiresAtUtc is not null && metadata.ExpiresAtUtc <= _clock.UtcNow)
            {
                return new HealthCheckResult
                {
                    Component = component,
                    Status = HealthStatus.Unhealthy,
                    Message = "Credencial expirada; novo registro necessário",
                    CheckedAtUtc = _clock.UtcNow
                };
            }

            // Proteção fraca em produção merece sinalização explícita.
            if (_credentialProtector is { IsHardened: false })
            {
                return new HealthCheckResult
                {
                    Component = component,
                    Status = HealthStatus.Degraded,
                    Message = $"Registrado, mas a credencial usa proteção não reforçada " +
                              $"({_credentialProtector.MechanismName})",
                    CheckedAtUtc = _clock.UtcNow
                };
            }

            var rotationThreshold = TimeSpan.FromDays(_portalOptions.CredentialRotationThresholdDays);
            if (metadata.ExpiresAtUtc is not null &&
                metadata.ExpiresAtUtc - _clock.UtcNow <= rotationThreshold)
            {
                return new HealthCheckResult
                {
                    Component = component,
                    Status = HealthStatus.Degraded,
                    Message = $"Credencial expira em {metadata.ExpiresAtUtc:o}; rotação recomendada",
                    CheckedAtUtc = _clock.UtcNow
                };
            }

            return new HealthCheckResult
            {
                Component = component,
                Status = HealthStatus.Healthy,
                Message = "Agent registrado e credencial válida",
                CheckedAtUtc = _clock.UtcNow
            };
        }
        catch (Exception ex)
        {
            return new HealthCheckResult
            {
                Component = component,
                Status = HealthStatus.Degraded,
                Message = $"Erro ao verificar registro: {ex.Message}",
                CheckedAtUtc = _clock.UtcNow
            };
        }
    }

    /// <summary>
    /// Estado da conexão WebSocket persistente com o Portal (seção 11). Desconectado não
    /// é necessariamente <c>unhealthy</c> — o backoff automático tenta de novo; só vira
    /// unhealthy quando as tentativas se acumulam além do razoável.
    /// </summary>
    private HealthCheckResult CheckWebSocketConnection()
    {
        const string component = "websocket";

        if (_portalOptions is null || !_portalOptions.Enabled)
        {
            return new HealthCheckResult
            {
                Component = component,
                Status = HealthStatus.Healthy,
                Message = "Integração com o Portal desabilitada",
                CheckedAtUtc = _clock.UtcNow
            };
        }

        if (_connectionManager is null)
        {
            return new HealthCheckResult
            {
                Component = component,
                Status = HealthStatus.Degraded,
                Message = "Gerenciador de conexão indisponível",
                CheckedAtUtc = _clock.UtcNow
            };
        }

        var status = _connectionManager.GetStatus();

        return status.State switch
        {
            ConnectionState.Connected => new HealthCheckResult
            {
                Component = component,
                Status = HealthStatus.Healthy,
                Message = $"Conectado desde {status.ConnectedAtUtc:o}",
                CheckedAtUtc = _clock.UtcNow
            },
            ConnectionState.Degraded => new HealthCheckResult
            {
                Component = component,
                Status = HealthStatus.Degraded,
                Message = "Conexão ativa, porém degradada",
                CheckedAtUtc = _clock.UtcNow
            },
            ConnectionState.Disabled => new HealthCheckResult
            {
                Component = component,
                Status = HealthStatus.Degraded,
                Message = "Conexão desabilitada manualmente",
                CheckedAtUtc = _clock.UtcNow
            },
            _ when status.ReconnectAttempt >= 5 => new HealthCheckResult
            {
                Component = component,
                Status = HealthStatus.Unhealthy,
                Message = $"Falha ao conectar após {status.ReconnectAttempt} tentativas " +
                          $"(último motivo: {status.DisconnectReason ?? "desconhecido"})",
                CheckedAtUtc = _clock.UtcNow
            },
            _ => new HealthCheckResult
            {
                Component = component,
                Status = HealthStatus.Degraded,
                Message = $"Estado atual: {status.State} (tentativa {status.ReconnectAttempt})",
                CheckedAtUtc = _clock.UtcNow
            }
        };
    }

    /// <summary>
    /// Uma conexão "Connected" sem <c>agent.heartbeat_ack</c> recente é sinal de que o
    /// Portal está recebendo mas não respondendo — diferente de "socket caiu", que já é
    /// coberto por <see cref="CheckWebSocketConnection"/>.
    /// </summary>
    private HealthCheckResult CheckHeartbeat()
    {
        const string component = "heartbeat";

        if (_portalOptions is null || !_portalOptions.Enabled)
        {
            return new HealthCheckResult
            {
                Component = component,
                Status = HealthStatus.Healthy,
                Message = "Integração com o Portal desabilitada",
                CheckedAtUtc = _clock.UtcNow
            };
        }

        if (_heartbeatService is null || _connectionManager is null)
        {
            return new HealthCheckResult
            {
                Component = component,
                Status = HealthStatus.Degraded,
                Message = "Serviço de heartbeat indisponível",
                CheckedAtUtc = _clock.UtcNow
            };
        }

        if (!ConnectionStateMachine.IsOperational(_connectionManager.CurrentState))
        {
            return new HealthCheckResult
            {
                Component = component,
                Status = HealthStatus.Degraded,
                Message = "Sem conexão ativa para enviar heartbeat",
                CheckedAtUtc = _clock.UtcNow
            };
        }

        if (_heartbeatService.LastSentAtUtc is null)
        {
            return new HealthCheckResult
            {
                Component = component,
                Status = HealthStatus.Degraded,
                Message = "Nenhum heartbeat enviado ainda",
                CheckedAtUtc = _clock.UtcNow
            };
        }

        var staleThreshold = TimeSpan.FromSeconds(_portalOptions.HeartbeatIntervalSeconds * 3);
        var sinceLastAck = _heartbeatService.LastAckAtUtc is null
            ? _clock.UtcNow - _heartbeatService.LastSentAtUtc.Value
            : _clock.UtcNow - _heartbeatService.LastAckAtUtc.Value;

        if (sinceLastAck > staleThreshold)
        {
            return new HealthCheckResult
            {
                Component = component,
                Status = HealthStatus.Degraded,
                Message = $"Sem agent.heartbeat_ack há {sinceLastAck.TotalSeconds:F0}s " +
                          $"(limite {staleThreshold.TotalSeconds:F0}s)",
                CheckedAtUtc = _clock.UtcNow
            };
        }

        return new HealthCheckResult
        {
            Component = component,
            Status = HealthStatus.Healthy,
            Message = $"Último ack em {_heartbeatService.LastAckAtUtc:o}",
            CheckedAtUtc = _clock.UtcNow
        };
    }

    private HealthCheckResult CheckExecutionHostAvailability()
    {
        try
        {
            var candidates = new[]
            {
                Path.Combine(AppContext.BaseDirectory, "ExecutionHost.exe"),
                Path.Combine(AppContext.BaseDirectory, "..", "Agent.ExecutionHost", "ExecutionHost.exe"),
            };

            var found = candidates.Any(File.Exists);
            return new HealthCheckResult
            {
                Component = "execution_host",
                Status = found ? HealthStatus.Healthy : HealthStatus.Degraded,
                Message = found ? "ExecutionHost.exe available" : "ExecutionHost.exe not found",
                CheckedAtUtc = _clock.UtcNow
            };
        }
        catch (Exception ex)
        {
            return new HealthCheckResult
            {
                Component = "execution_host",
                Status = HealthStatus.Degraded,
                Message = $"ExecutionHost check error: {ex.Message}",
                CheckedAtUtc = _clock.UtcNow
            };
        }
    }
}
