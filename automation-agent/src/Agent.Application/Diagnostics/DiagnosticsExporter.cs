using Biason.AutomationAgent.Application.HealthChecks;
using Biason.AutomationAgent.Application.Sessions;
using Biason.AutomationAgent.Domain.Contracts;
using System.Text.Json;
using Microsoft.Extensions.Logging;

namespace Biason.AutomationAgent.Application.Diagnostics;

public sealed class DiagnosticsExporter
{
    private readonly IAgentIdentityService _identity;
    private readonly IAgentStateManager _stateManager;
    private readonly IMachineProfiler _profiler;
    private readonly HealthCheckRunner _healthRunner;
    private readonly IDirectoryResolver _dirs;
    private readonly IClock _clock;
    private readonly IAgentCredentialStore? _credentialStore;
    private readonly ICredentialProtector? _credentialProtector;
    private readonly IOutboxRepository? _outbox;
    private readonly IInboxRepository? _inbox;
    private readonly IInteractiveSessionRepository? _interactiveSessions;
    private readonly ISessionRunnerRepository? _sessionRunners;
    private readonly ISessionRunnerConnectionRepository? _sessionRunnerConnections;
    private readonly ISessionEventRepository? _sessionEvents;
    private readonly SessionRunnerPipeServer? _sessionRunnerPipeServer;
    private readonly IInteractivePoolService? _interactivePool;
    private readonly IDesktopLockManager? _desktopLocks;
    private readonly IInteractiveExecutionAssignmentRepository? _interactiveAssignments;
    private readonly IInteractiveExecutionProcessRepository? _interactiveProcesses;
    private readonly IApplicationProcessOwnershipRepository? _applicationProcesses;
    private readonly ILogger<DiagnosticsExporter> _logger;
    private static readonly JsonSerializerOptions JsonOpts = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        WriteIndented = true
    };

    public DiagnosticsExporter(
        IAgentIdentityService identity,
        IAgentStateManager stateManager,
        IMachineProfiler profiler,
        HealthCheckRunner healthRunner,
        IDirectoryResolver dirs,
        IClock clock,
        ILogger<DiagnosticsExporter> logger,
        IAgentCredentialStore? credentialStore = null,
        ICredentialProtector? credentialProtector = null,
        IOutboxRepository? outbox = null,
        IInboxRepository? inbox = null,
        IInteractiveSessionRepository? interactiveSessions = null,
        ISessionRunnerRepository? sessionRunners = null,
        ISessionRunnerConnectionRepository? sessionRunnerConnections = null,
        ISessionEventRepository? sessionEvents = null,
        SessionRunnerPipeServer? sessionRunnerPipeServer = null,
        IInteractivePoolService? interactivePool = null,
        IDesktopLockManager? desktopLocks = null,
        IInteractiveExecutionAssignmentRepository? interactiveAssignments = null,
        IInteractiveExecutionProcessRepository? interactiveProcesses = null,
        IApplicationProcessOwnershipRepository? applicationProcesses = null)
    {
        _identity = identity;
        _stateManager = stateManager;
        _profiler = profiler;
        _healthRunner = healthRunner;
        _dirs = dirs;
        _clock = clock;
        _credentialStore = credentialStore;
        _credentialProtector = credentialProtector;
        _outbox = outbox;
        _inbox = inbox;
        _interactiveSessions = interactiveSessions;
        _sessionRunners = sessionRunners;
        _sessionRunnerConnections = sessionRunnerConnections;
        _sessionEvents = sessionEvents;
        _sessionRunnerPipeServer = sessionRunnerPipeServer;
        _interactivePool = interactivePool;
        _desktopLocks = desktopLocks;
        _interactiveAssignments = interactiveAssignments;
        _interactiveProcesses = interactiveProcesses;
        _applicationProcesses = applicationProcesses;
        _logger = logger;
    }

    public async Task<string> ExportAsync(CancellationToken ct = default)
    {
        var timestamp = _clock.UtcNow.ToString("yyyyMMdd-HHmmss");
        var exportDir = Path.Combine(_dirs.DiagnosticsPath, $"diag-{timestamp}");
        Directory.CreateDirectory(exportDir);

        // agent-info.json
        var identity = await _identity.GetIdentityAsync(ct);
        var agentInfo = new
        {
            installation_id = identity?.InstallationId,
            agent_id = identity?.AgentId,
            instance_id = identity?.InstanceId,
            machine_id = identity?.MachineId,
            state = _stateManager.CurrentState.ToString(),
            exported_at_utc = _clock.UtcNow
        };
        await File.WriteAllTextAsync(Path.Combine(exportDir, "agent-info.json"), JsonSerializer.Serialize(agentInfo, JsonOpts), ct);

        // machine-profile.json
        try
        {
            var profile = await _profiler.CaptureProfileAsync(ct);
            await File.WriteAllTextAsync(Path.Combine(exportDir, "machine-profile.json"), JsonSerializer.Serialize(profile, JsonOpts), ct);
        }
        catch (Exception ex)
        {
            await File.WriteAllTextAsync(Path.Combine(exportDir, "machine-profile.json"), JsonSerializer.Serialize(new { error = ex.Message }, JsonOpts), ct);
        }

        // health.json
        var health = await _healthRunner.RunAllAsync(ct);
        await File.WriteAllTextAsync(Path.Combine(exportDir, "health.json"), JsonSerializer.Serialize(health, JsonOpts), ct);

        // registration-status.json
        // Deliberadamente sem tokens, credenciais ou qualquer material sensível:
        // apenas fingerprint irreversível, datas e mecanismo de proteção.
        var credentialMetadata = _credentialStore is null
            ? null
            : await _credentialStore.GetMetadataAsync(ct);

        var registrationStatus = new
        {
            registered = identity?.IsRegistered ?? false,
            agent_id = identity?.AgentId,
            installation_id = identity?.InstallationId,
            registered_at_utc = identity?.RegisteredAtUtc,
            credential = credentialMetadata is null
                ? null
                : new
                {
                    type = credentialMetadata.Type,
                    fingerprint = credentialMetadata.Fingerprint,
                    stored_at_utc = credentialMetadata.StoredAtUtc,
                    expires_at_utc = credentialMetadata.ExpiresAtUtc,
                    last_used_at_utc = credentialMetadata.LastUsedAtUtc,
                    revoked = credentialMetadata.IsRevoked,
                    revoked_at_utc = credentialMetadata.RevokedAtUtc
                },
            protection = _credentialProtector is null
                ? null
                : new
                {
                    mechanism = _credentialProtector.MechanismName,
                    hardened = _credentialProtector.IsHardened
                },
            exported_at_utc = _clock.UtcNow
        };
        await File.WriteAllTextAsync(
            Path.Combine(exportDir, "registration-status.json"),
            JsonSerializer.Serialize(registrationStatus, JsonOpts), ct);

        // database-summary.json
        var dbSummary = new
        {
            path = _dirs.DatabaseFilePath,
            exists = File.Exists(_dirs.DatabaseFilePath),
            size_kb = File.Exists(_dirs.DatabaseFilePath) ? new FileInfo(_dirs.DatabaseFilePath).Length / 1024 : 0
        };
        await File.WriteAllTextAsync(Path.Combine(exportDir, "database-summary.json"), JsonSerializer.Serialize(dbSummary, JsonOpts), ct);

        if (_outbox is not null && _inbox is not null)
        {
            var messaging = new
            {
                outbox = await _outbox.GetDiagnosticsAsync(ct),
                inbox = await _inbox.GetDiagnosticsAsync(ct),
                exported_at_utc = _clock.UtcNow
            };
            await File.WriteAllTextAsync(
                Path.Combine(exportDir, "messaging-diagnostics.json"),
                JsonSerializer.Serialize(messaging, JsonOpts),
                ct);
        }

        // configuration-summary.json (sanitized — no secrets)
        if (_interactiveSessions is not null)
        {
            await File.WriteAllTextAsync(
                Path.Combine(exportDir, "sessions.json"),
                JsonSerializer.Serialize(await _interactiveSessions.GetAllAsync(ct), JsonOpts),
                ct);
        }

        if (_sessionRunners is not null)
        {
            var runners = (await _sessionRunners.GetAllAsync(ct)).Select(r => new
            {
                r.InstanceId,
                r.SessionId,
                r.UserName,
                r.SessionType,
                r.ProcessId,
                r.Version,
                r.Desktop,
                r.State,
                r.RegisteredAtUtc,
                r.LastHeartbeatAtUtc,
                r.DisconnectedAtUtc
            });

            await File.WriteAllTextAsync(
                Path.Combine(exportDir, "session-runners.json"),
                JsonSerializer.Serialize(runners, JsonOpts),
                ct);
        }

        if (_sessionRunnerConnections is not null)
        {
            await File.WriteAllTextAsync(
                Path.Combine(exportDir, "session-runner-connections.json"),
                JsonSerializer.Serialize(await _sessionRunnerConnections.GetRecentAsync(100, ct), JsonOpts),
                ct);
        }

        if (_sessionRunnerPipeServer is not null)
        {
            await File.WriteAllTextAsync(
                Path.Combine(exportDir, "named-pipe-status.json"),
                JsonSerializer.Serialize(_sessionRunnerPipeServer.GetStatus(), JsonOpts),
                ct);
        }

        if (_sessionEvents is not null)
        {
            await File.WriteAllTextAsync(
                Path.Combine(exportDir, "recent-session-events.json"),
                JsonSerializer.Serialize(await _sessionEvents.GetRecentAsync(100, ct), JsonOpts),
                ct);
        }

        if (_interactivePool is not null)
        {
            await File.WriteAllTextAsync(
                Path.Combine(exportDir, "interactive-pool.json"),
                JsonSerializer.Serialize(new
                {
                    active = await _interactivePool.CountActiveAsync(ct),
                    exported_at_utc = _clock.UtcNow
                }, JsonOpts),
                ct);
        }

        if (_desktopLocks is not null)
        {
            await File.WriteAllTextAsync(
                Path.Combine(exportDir, "desktop-locks.json"),
                JsonSerializer.Serialize(await _desktopLocks.GetAllAsync(ct), JsonOpts),
                ct);
        }

        if (_interactiveAssignments is not null)
        {
            await File.WriteAllTextAsync(
                Path.Combine(exportDir, "interactive-executions.json"),
                JsonSerializer.Serialize(await _interactiveAssignments.GetAllAsync(ct), JsonOpts),
                ct);
        }

        if (_applicationProcesses is not null)
        {
            await File.WriteAllTextAsync(
                Path.Combine(exportDir, "application-processes.json"),
                JsonSerializer.Serialize(await _applicationProcesses.GetAllAsync(ct), JsonOpts),
                ct);
        }

        if (_interactiveProcesses is not null)
        {
            await File.WriteAllTextAsync(
                Path.Combine(exportDir, "interactive-processes.json"),
                JsonSerializer.Serialize(await _interactiveProcesses.GetAllAsync(ct), JsonOpts),
                ct);
        }

        var configSummary = new
        {
            data_directory = _dirs.RootPath,
            log_directory = _dirs.LogsPath,
            database_directory = _dirs.DatabasePath
        };
        await File.WriteAllTextAsync(Path.Combine(exportDir, "configuration-summary.json"), JsonSerializer.Serialize(configSummary, JsonOpts), ct);

        // recent-logs/
        var recentLogsDir = Path.Combine(exportDir, "recent-logs");
        Directory.CreateDirectory(recentLogsDir);
        try
        {
            if (Directory.Exists(_dirs.LogsPath))
            {
                foreach (var logFile in Directory.GetFiles(_dirs.LogsPath, "*.log").OrderByDescending(f => File.GetLastWriteTimeUtc(f)).Take(3))
                {
                    File.Copy(logFile, Path.Combine(recentLogsDir, Path.GetFileName(logFile)), overwrite: true);
                }
            }
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to copy recent logs for diagnostics");
        }

        _logger.LogInformation("Diagnostics exported to {Path}", exportDir);
        return exportDir;
    }
}
