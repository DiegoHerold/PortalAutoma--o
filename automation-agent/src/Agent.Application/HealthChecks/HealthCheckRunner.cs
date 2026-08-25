using Biason.AutomationAgent.Application.Heartbeat;
using Biason.AutomationAgent.Application.Messaging;
using Biason.AutomationAgent.Application.Sessions;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models;
using Biason.AutomationAgent.Domain.StateMachines;
using Biason.AutomationAgent.Protocol.Messages;
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
    private readonly IOutboxRepository? _outbox;
    private readonly IInboxRepository? _inbox;
    private readonly IWindowsSessionDiscovery? _sessionDiscovery;
    private readonly ISessionRunnerRegistry? _sessionRunnerRegistry;
    private readonly SessionRunnerPipeServer? _sessionRunnerPipeServer;
    private readonly IInteractiveSessionRepository? _interactiveSessions;
    private readonly IInteractivePoolService? _interactivePool;
    private readonly IDesktopLockManager? _desktopLocks;
    private readonly IInteractiveExecutionAssignmentRepository? _interactiveAssignments;
    private readonly IEnumerable<IInboxCommandHandler>? _commandHandlers;
    private readonly IExecutionLeaseManager? _leaseManager;
    private readonly IArtifactManager? _artifactManager;
    private readonly IArtifactUploadManager? _artifactUploadManager;
    private readonly IPendingArtifactRepository? _pendingArtifacts;
    private readonly IAgentSyncService? _syncService;
    private readonly ISyncRunRepository? _syncRuns;
    private readonly Domain.Configuration.SessionRunnerOptions? _sessionRunnerOptions;
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
        HeartbeatService? heartbeatService = null,
        IOutboxRepository? outbox = null,
        IInboxRepository? inbox = null,
        IWindowsSessionDiscovery? sessionDiscovery = null,
        ISessionRunnerRegistry? sessionRunnerRegistry = null,
        SessionRunnerPipeServer? sessionRunnerPipeServer = null,
        IInteractiveSessionRepository? interactiveSessions = null,
        Microsoft.Extensions.Options.IOptions<Domain.Configuration.SessionRunnerOptions>? sessionRunnerOptions = null,
        IInteractivePoolService? interactivePool = null,
        IDesktopLockManager? desktopLocks = null,
        IInteractiveExecutionAssignmentRepository? interactiveAssignments = null,
        IEnumerable<IInboxCommandHandler>? commandHandlers = null,
        IExecutionLeaseManager? leaseManager = null,
        IArtifactManager? artifactManager = null,
        IArtifactUploadManager? artifactUploadManager = null,
        IPendingArtifactRepository? pendingArtifacts = null,
        IAgentSyncService? syncService = null,
        ISyncRunRepository? syncRuns = null)
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
        _outbox = outbox;
        _inbox = inbox;
        _sessionDiscovery = sessionDiscovery;
        _sessionRunnerRegistry = sessionRunnerRegistry;
        _sessionRunnerPipeServer = sessionRunnerPipeServer;
        _interactiveSessions = interactiveSessions;
        _interactivePool = interactivePool;
        _desktopLocks = desktopLocks;
        _interactiveAssignments = interactiveAssignments;
        _commandHandlers = commandHandlers;
        _leaseManager = leaseManager;
        _artifactManager = artifactManager;
        _artifactUploadManager = artifactUploadManager;
        _pendingArtifacts = pendingArtifacts;
        _syncService = syncService;
        _syncRuns = syncRuns;
        _sessionRunnerOptions = sessionRunnerOptions?.Value;
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
            CheckHeartbeat(),
            await CheckDurableMessagingAsync(ct),
            CheckPortalCommandHandlers(),
            CheckReservationRehydration(),
            CheckLeaseManager(),
            await CheckArtifactManagerAsync(ct),
            await CheckSyncManagerAsync(ct),
            await CheckWindowsSessionDiscoveryAsync(ct),
            await CheckSessionRunnerRegistryAsync(ct),
            CheckSessionRunnerPipe(),
            await CheckInteractiveSessionsAsync(ct),
            await CheckInteractivePoolAsync(ct),
            await CheckDesktopLocksAsync(ct),
            await CheckInteractiveExecutionAsync(ct),
            CheckDesktopLauncher(),
            CheckPythonDesktopRuntime()
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
                Path.Combine(AppContext.BaseDirectory, "..", "Agent.ExecutionHost", "bin", "Debug", "net8.0", "win-x64", "ExecutionHost.exe"),
                Path.Combine(AppContext.BaseDirectory, "..", "Agent.ExecutionHost", "bin", "Release", "net8.0", "win-x64", "ExecutionHost.exe"),
                Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "Agent.ExecutionHost", "bin", "Debug", "net8.0", "win-x64", "ExecutionHost.exe"),
                Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "Agent.ExecutionHost", "bin", "Release", "net8.0", "win-x64", "ExecutionHost.exe"),
                Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "..", "artifacts", "publish", "AgentService", "ExecutionHost.exe"),
                Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "..", "artifacts", "publish", "ExecutionHost", "ExecutionHost.exe"),
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

    private HealthCheckResult CheckDesktopLauncher()
    {
        try
        {
            var candidates = new[]
            {
                Path.Combine(AppContext.BaseDirectory, "ExecutionHost.exe"),
                Path.Combine(AppContext.BaseDirectory, "..", "Agent.ExecutionHost", "ExecutionHost.exe"),
                Path.Combine(AppContext.BaseDirectory, "..", "Agent.ExecutionHost", "bin", "Debug", "net8.0", "win-x64", "ExecutionHost.exe"),
                Path.Combine(AppContext.BaseDirectory, "..", "Agent.ExecutionHost", "bin", "Release", "net8.0", "win-x64", "ExecutionHost.exe"),
                Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "Agent.ExecutionHost", "bin", "Debug", "net8.0", "win-x64", "ExecutionHost.exe"),
                Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "Agent.ExecutionHost", "bin", "Release", "net8.0", "win-x64", "ExecutionHost.exe"),
                Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "..", "artifacts", "publish", "AgentService", "ExecutionHost.exe"),
                Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "..", "artifacts", "publish", "ExecutionHost", "ExecutionHost.exe"),
            };
            var found = candidates.Any(File.Exists);
            return new HealthCheckResult
            {
                Component = "desktop_launcher",
                Status = found ? HealthStatus.Healthy : HealthStatus.Degraded,
                Message = found ? "Interactive desktop launcher can resolve ExecutionHost.exe" : "ExecutionHost.exe not found for interactive launcher",
                CheckedAtUtc = _clock.UtcNow
            };
        }
        catch (Exception ex)
        {
            return new HealthCheckResult
            {
                Component = "desktop_launcher",
                Status = HealthStatus.Degraded,
                Message = $"Desktop launcher check error: {ex.Message}",
                CheckedAtUtc = _clock.UtcNow
            };
        }
    }

    private HealthCheckResult CheckPythonDesktopRuntime()
    {
        try
        {
            var root = _dirs.RuntimesPath;
            var candidates = new[]
            {
                Path.Combine(root, "python-desktop", "latest"),
                Path.Combine(root, "python-desktop", "3.13"),
                Path.Combine(root, "python-desktop-3.13", "latest")
            };
            var found = candidates.Any(Directory.Exists);
            return new HealthCheckResult
            {
                Component = "python_desktop_runtime",
                Status = found ? HealthStatus.Healthy : HealthStatus.Degraded,
                Message = found ? "python-desktop runtime found" : "python-desktop runtime not installed in local store",
                CheckedAtUtc = _clock.UtcNow
            };
        }
        catch (Exception ex)
        {
            return new HealthCheckResult
            {
                Component = "python_desktop_runtime",
                Status = HealthStatus.Degraded,
                Message = $"python-desktop runtime check error: {ex.Message}",
                CheckedAtUtc = _clock.UtcNow
            };
        }
    }

    private async Task<HealthCheckResult> CheckWindowsSessionDiscoveryAsync(CancellationToken ct)
    {
        if (_sessionDiscovery is null)
            return NotConfigured("windows_session_discovery");

        try
        {
            var sessions = await _sessionDiscovery.DiscoverAsync(ct);
            return new HealthCheckResult
            {
                Component = "windows_session_discovery",
                Status = HealthStatus.Healthy,
                Message = $"Discovered {sessions.Count} Windows session(s)",
                CheckedAtUtc = _clock.UtcNow
            };
        }
        catch (Exception ex)
        {
            return new HealthCheckResult
            {
                Component = "windows_session_discovery",
                Status = HealthStatus.Degraded,
                Message = $"Session discovery failed: {ex.Message}",
                CheckedAtUtc = _clock.UtcNow
            };
        }
    }

    private async Task<HealthCheckResult> CheckSessionRunnerRegistryAsync(CancellationToken ct)
    {
        if (_sessionRunnerRegistry is null)
            return NotConfigured("session_runner_registry");

        try
        {
            var runners = await _sessionRunnerRegistry.GetSnapshotAsync(ct);
            var connected = runners.Count(r => r.State == SessionRunnerConnectionState.Connected);
            return new HealthCheckResult
            {
                Component = "session_runner_registry",
                Status = HealthStatus.Healthy,
                Message = $"{connected} connected Session Runner(s), {runners.Count} known",
                CheckedAtUtc = _clock.UtcNow
            };
        }
        catch (Exception ex)
        {
            return new HealthCheckResult
            {
                Component = "session_runner_registry",
                Status = HealthStatus.Degraded,
                Message = $"Session Runner registry check failed: {ex.Message}",
                CheckedAtUtc = _clock.UtcNow
            };
        }
    }

    private HealthCheckResult CheckSessionRunnerPipe()
    {
        if (_sessionRunnerPipeServer is null)
            return NotConfigured("session_runner_pipe");

        return new HealthCheckResult
        {
            Component = "session_runner_pipe",
            Status = HealthStatus.Healthy,
            Message = "Session Runner named pipe server is configured",
            CheckedAtUtc = _clock.UtcNow
        };
    }

    private async Task<HealthCheckResult> CheckInteractiveSessionsAsync(CancellationToken ct)
    {
        if (_interactiveSessions is null)
            return NotConfigured("interactive_sessions");

        try
        {
            var sessions = await _interactiveSessions.GetAllAsync(ct);
            var active = sessions.Where(s => s.State == WindowsSessionState.Active).ToList();
            var activeWithoutRunner = active.Count(s => s.SessionRunnerInstanceId is null);
            var status = _sessionRunnerOptions?.ExpectRunnerForActiveSessions == true && activeWithoutRunner > 0
                ? HealthStatus.Degraded
                : HealthStatus.Healthy;

            return new HealthCheckResult
            {
                Component = "interactive_sessions",
                Status = status,
                Message = active.Count == 0
                    ? "No active interactive sessions; interactive unavailable"
                    : $"{active.Count} active session(s), {activeWithoutRunner} without runner",
                CheckedAtUtc = _clock.UtcNow
            };
        }
        catch (Exception ex)
        {
            return new HealthCheckResult
            {
                Component = "interactive_sessions",
                Status = HealthStatus.Degraded,
                Message = $"Interactive session check failed: {ex.Message}",
                CheckedAtUtc = _clock.UtcNow
            };
        }
    }

    private async Task<HealthCheckResult> CheckInteractivePoolAsync(CancellationToken ct)
    {
        if (_interactivePool is null)
            return NotConfigured("interactive_pool");

        try
        {
            var active = await _interactivePool.CountActiveAsync(ct);
            return new HealthCheckResult
            {
                Component = "interactive_pool",
                Status = active <= 1 ? HealthStatus.Healthy : HealthStatus.Unhealthy,
                Message = $"{active} active interactive execution(s)",
                CheckedAtUtc = _clock.UtcNow
            };
        }
        catch (Exception ex)
        {
            return new HealthCheckResult
            {
                Component = "interactive_pool",
                Status = HealthStatus.Degraded,
                Message = $"Interactive pool check failed: {ex.Message}",
                CheckedAtUtc = _clock.UtcNow
            };
        }
    }

    private async Task<HealthCheckResult> CheckDesktopLocksAsync(CancellationToken ct)
    {
        if (_desktopLocks is null)
            return NotConfigured("desktop_locks");

        try
        {
            var recovered = await _desktopLocks.RecoverExpiredAsync(ct);
            var locks = await _desktopLocks.GetAllAsync(ct);
            var active = locks.Count(l => l.Status is DesktopLockStatus.Reserved or DesktopLockStatus.Committed or DesktopLockStatus.Active);
            return new HealthCheckResult
            {
                Component = "desktop_locks",
                Status = HealthStatus.Healthy,
                Message = $"{active} active desktop lock(s), {recovered} expired lock(s) recovered",
                CheckedAtUtc = _clock.UtcNow
            };
        }
        catch (Exception ex)
        {
            return new HealthCheckResult
            {
                Component = "desktop_locks",
                Status = HealthStatus.Degraded,
                Message = $"Desktop lock check failed: {ex.Message}",
                CheckedAtUtc = _clock.UtcNow
            };
        }
    }

    private async Task<HealthCheckResult> CheckInteractiveExecutionAsync(CancellationToken ct)
    {
        if (_interactiveAssignments is null)
            return NotConfigured("interactive_execution");

        try
        {
            var active = await _interactiveAssignments.GetActiveAsync(ct);
            var status = active.Count <= 1 ? HealthStatus.Healthy : HealthStatus.Unhealthy;
            return new HealthCheckResult
            {
                Component = "interactive_execution",
                Status = status,
                Message = $"{active.Count} active interactive assignment(s)",
                CheckedAtUtc = _clock.UtcNow
            };
        }
        catch (Exception ex)
        {
            return new HealthCheckResult
            {
                Component = "interactive_execution",
                Status = HealthStatus.Degraded,
                Message = $"Interactive execution check failed: {ex.Message}",
                CheckedAtUtc = _clock.UtcNow
            };
        }
    }

    private HealthCheckResult NotConfigured(string component) => new()
    {
        Component = component,
        Status = HealthStatus.Degraded,
        Message = $"{component} is not configured",
        CheckedAtUtc = _clock.UtcNow
    };

    private HealthCheckResult CheckPortalCommandHandlers()
    {
        const string component = "portal_command_handlers";

        if (_commandHandlers is null)
            return NotConfigured(component);

        var registered = _commandHandlers.Select(h => h.MessageType).ToHashSet(StringComparer.Ordinal);
        var missing = PortalMessageTypes.Commands.Where(c => !registered.Contains(c)).ToArray();

        return new HealthCheckResult
        {
            Component = component,
            Status = missing.Length == 0 ? HealthStatus.Healthy : HealthStatus.Unhealthy,
            Message = missing.Length == 0
                ? $"{registered.Count} portal command handler(s) registered"
                : $"Missing handler(s): {string.Join(", ", missing)}",
            CheckedAtUtc = _clock.UtcNow
        };
    }

    private HealthCheckResult CheckReservationRehydration()
    {
        return new HealthCheckResult
        {
            Component = "reservation_rehydration",
            Status = _capacityManager is null ? HealthStatus.Unhealthy : HealthStatus.Healthy,
            Message = _capacityManager is null
                ? "Capacity manager unavailable; persisted reservations cannot be rehydrated"
                : "Capacity manager exposes reservation rehydration",
            CheckedAtUtc = _clock.UtcNow
        };
    }

    private HealthCheckResult CheckLeaseManager()
    {
        return new HealthCheckResult
        {
            Component = "lease_manager",
            Status = _leaseManager is null ? HealthStatus.Unhealthy : HealthStatus.Healthy,
            Message = _leaseManager is null ? "Execution lease manager unavailable" : "Execution lease manager configured",
            CheckedAtUtc = _clock.UtcNow
        };
    }

    private async Task<HealthCheckResult> CheckArtifactManagerAsync(CancellationToken ct)
    {
        const string component = "artifact_manager";

        if (_artifactManager is null || _artifactUploadManager is null || _pendingArtifacts is null)
        {
            return new HealthCheckResult
            {
                Component = component,
                Status = HealthStatus.Unhealthy,
                Message = "Artifact manager, upload manager, or repository is unavailable",
                CheckedAtUtc = _clock.UtcNow
            };
        }

        var diagnostics = await _pendingArtifacts.GetDiagnosticsAsync(ct);
        return new HealthCheckResult
        {
            Component = component,
            Status = diagnostics.Failed > 0 ? HealthStatus.Degraded : HealthStatus.Healthy,
            Message = $"pending={diagnostics.Pending}, announced={diagnostics.Announced}, upload_url_received={diagnostics.UploadUrlReceived}, " +
                      $"uploading={diagnostics.Uploading}, uploaded={diagnostics.Uploaded}, " +
                      $"confirmed={diagnostics.Confirmed}, retry_wait={diagnostics.RetryWait}, failed={diagnostics.Failed}",
            CheckedAtUtc = _clock.UtcNow
        };
    }

    private async Task<HealthCheckResult> CheckSyncManagerAsync(CancellationToken ct)
    {
        const string component = "sync_manager";

        if (_syncService is null || _syncRuns is null)
        {
            return new HealthCheckResult
            {
                Component = component,
                Status = HealthStatus.Unhealthy,
                Message = "Agent sync service or sync run repository is unavailable",
                CheckedAtUtc = _clock.UtcNow
            };
        }

        var latest = await _syncRuns.GetLatestAsync(ct);
        return new HealthCheckResult
        {
            Component = component,
            Status = latest?.Status == "failed" ? HealthStatus.Degraded : HealthStatus.Healthy,
            Message = latest is null
                ? "Sync manager configured; no sync run recorded yet"
                : $"Last sync {latest.SyncId} status={latest.Status}, completed_at={latest.CompletedAtUtc:o}",
            CheckedAtUtc = _clock.UtcNow
        };
    }

    private async Task<HealthCheckResult> CheckDurableMessagingAsync(CancellationToken ct)
    {
        const string component = "durable_messaging";

        if (_outbox is null || _inbox is null)
        {
            return new HealthCheckResult
            {
                Component = component,
                Status = HealthStatus.Degraded,
                Message = "Outbox/Inbox repositories unavailable",
                CheckedAtUtc = _clock.UtcNow
            };
        }

        try
        {
            var outbox = await _outbox.GetDiagnosticsAsync(ct);
            var inbox = await _inbox.GetDiagnosticsAsync(ct);
            var deadLetters = outbox.DeadLetter + inbox.DeadLetter;

            return new HealthCheckResult
            {
                Component = component,
                Status = deadLetters > 0 ? HealthStatus.Degraded : HealthStatus.Healthy,
                Message = $"Outbox pending={outbox.Pending}, sent_unacked={outbox.Sent}, dead_letter={outbox.DeadLetter}; " +
                          $"Inbox pending={inbox.Pending}, processing={inbox.Processing}, dead_letter={inbox.DeadLetter}",
                CheckedAtUtc = _clock.UtcNow
            };
        }
        catch (Exception ex)
        {
            return new HealthCheckResult
            {
                Component = component,
                Status = HealthStatus.Degraded,
                Message = $"Durable messaging check error: {ex.Message}",
                CheckedAtUtc = _clock.UtcNow
            };
        }
    }
}
