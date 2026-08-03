using System.Text.Json;
using Biason.AutomationAgent.Application.Diagnostics;
using Biason.AutomationAgent.Application.HealthChecks;
using Biason.AutomationAgent.Application.Services;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Infrastructure.Persistence;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

namespace Biason.AutomationAgent.Service;

public sealed class AgentWorker : BackgroundService
{
    private readonly IHostApplicationLifetime _lifetime;
    private readonly IDirectoryResolver _dirs;
    private readonly Infrastructure.Database.SqliteDatabaseManager _dbManager;
    private readonly AgentStateManagerImpl _stateManager;
    private readonly IAgentIdentityService _identityService;
    private readonly IMachineProfiler _profiler;
    private readonly ICapabilityDetector _capabilityDetector;
    private readonly ICapabilityRepository _capabilityRepo;
    private readonly IMachineProfileRepository _profileRepo;
    private readonly HealthCheckRunner _healthRunner;
    private readonly MachineReportGenerator _reportGenerator;
    private readonly DiagnosticsExporter _diagnosticsExporter;
    private readonly IExecutionManager _executionManager;
    private readonly IResourceReservationManager _reservationManager;
    private readonly ICacheManager _cacheManager;
    private readonly IAgentRegistrationService _registration;
    private readonly IAgentCredentialStore _credentialStore;
    private readonly ICredentialProtector _credentialProtector;
    private readonly IPortalConnectionManager _connectionManager;
    private readonly IConnectionStateRepository _connectionStateRepo;
    private readonly ILogger<AgentWorker> _logger;

    private static readonly JsonSerializerOptions JsonOpts = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        WriteIndented = true
    };

    public AgentWorker(
        IHostApplicationLifetime lifetime,
        IDirectoryResolver dirs,
        Infrastructure.Database.SqliteDatabaseManager dbManager,
        AgentStateManagerImpl stateManager,
        IAgentIdentityService identityService,
        IMachineProfiler profiler,
        ICapabilityDetector capabilityDetector,
        ICapabilityRepository capabilityRepo,
        IMachineProfileRepository profileRepo,
        HealthCheckRunner healthRunner,
        MachineReportGenerator reportGenerator,
        DiagnosticsExporter diagnosticsExporter,
        IExecutionManager executionManager,
        IResourceReservationManager reservationManager,
        ICacheManager cacheManager,
        IAgentRegistrationService registration,
        IAgentCredentialStore credentialStore,
        ICredentialProtector credentialProtector,
        IPortalConnectionManager connectionManager,
        IConnectionStateRepository connectionStateRepo,
        ILogger<AgentWorker> logger)
    {
        _lifetime = lifetime;
        _dirs = dirs;
        _dbManager = dbManager;
        _stateManager = stateManager;
        _identityService = identityService;
        _profiler = profiler;
        _capabilityDetector = capabilityDetector;
        _capabilityRepo = capabilityRepo;
        _profileRepo = profileRepo;
        _healthRunner = healthRunner;
        _reportGenerator = reportGenerator;
        _diagnosticsExporter = diagnosticsExporter;
        _executionManager = executionManager;
        _reservationManager = reservationManager;
        _cacheManager = cacheManager;
        _registration = registration;
        _credentialStore = credentialStore;
        _credentialProtector = credentialProtector;
        _connectionManager = connectionManager;
        _connectionStateRepo = connectionStateRepo;
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        try
        {
            // === STARTING ===
            _logger.LogInformation("Biason Automation Agent starting...");

            // Validate and create directories
            if (!_dirs.Validate(out var errors))
            {
                _logger.LogError("Directory validation failed: {Errors}", string.Join("; ", errors));
                await TransitionToFaulted("Directory validation failed", stoppingToken);
                return;
            }
            _dirs.EnsureDirectoriesExist();

            // Initialize database
            try
            {
                await _dbManager.InitializeAsync(stoppingToken);
            }
            catch (Exception ex)
            {
                _logger.LogCritical(ex, "Failed to initialize database");
                await TransitionToFaulted("Database initialization failed", stoppingToken);
                return;
            }

            // Load persisted state
            await _stateManager.LoadPersistedStateAsync(stoppingToken);

            // === INITIALIZING ===
            await _stateManager.TransitionToAsync(AgentState.Initializing, "Startup sequence", source: "agent_worker", ct: stoppingToken);

            // Create/load identity
            var identity = await _identityService.GetOrCreateIdentityAsync(stoppingToken);
            _logger.LogInformation("Agent identity: InstallationId={InstallationId}, InstanceId={InstanceId}",
                identity.InstallationId, identity.InstanceId);

            // Machine profiling
            _logger.LogInformation("Running machine profiler...");
            var profile = await _profiler.CaptureProfileAsync(stoppingToken);
            await _profileRepo.SaveAsync(profile, stoppingToken);

            // Capability detection
            _logger.LogInformation("Detecting capabilities...");
            var capabilities = await _capabilityDetector.DetectAllAsync(stoppingToken);
            await _capabilityRepo.SaveAllAsync(capabilities, stoppingToken);

            // Registro no Portal — idempotente: não gera novo registro se já houver
            // agent_id com credencial válida. Falha aqui NÃO impede o Agent de subir;
            // ele segue funcional localmente e o health check reporta 'degraded'.
            try
            {
                var registrationResult = await _registration.EnsureRegisteredAsync(stoppingToken);
                _logger.LogInformation("Registro no Portal: {Outcome} (agent_id={AgentId})",
                    registrationResult.Outcome, registrationResult.AgentId ?? "-");
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
            {
                throw;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Registro no Portal falhou; o Agent seguirá em modo local.");
            }

            // Recover orphaned executions and stale reservations
            _logger.LogInformation("Recovering orphaned executions...");
            await _executionManager.RecoverOrphanedAsync(stoppingToken);
            await _reservationManager.ExpireStaleAsync(stoppingToken);

            // Health checks
            var healthResults = await _healthRunner.RunAllAsync(stoppingToken);
            var overallHealth = _healthRunner.GetOverallStatus(healthResults);

            // Transition to READY or DEGRADED
            if (overallHealth == HealthStatus.Unhealthy)
            {
                await _stateManager.TransitionToAsync(AgentState.Degraded,
                    "Health checks reported unhealthy components",
                    source: "agent_worker", ct: stoppingToken);
            }
            else if (overallHealth == HealthStatus.Degraded)
            {
                await _stateManager.TransitionToAsync(AgentState.Degraded,
                    "Health checks reported degraded components",
                    source: "agent_worker", ct: stoppingToken);
            }
            else
            {
                await _stateManager.TransitionToAsync(AgentState.Ready,
                    "Initialization complete",
                    source: "agent_worker", ct: stoppingToken);
            }

            _logger.LogInformation("Agent is {State}. Waiting for commands...", _stateManager.CurrentState);

            // Check for profile command
            if (Environment.GetCommandLineArgs().Contains("profile", StringComparer.OrdinalIgnoreCase))
            {
                var report = await _reportGenerator.GenerateAsync(stoppingToken);
                var json = JsonSerializer.Serialize(report, JsonOpts);
                Console.WriteLine(json);

                var reportPath = Path.Combine(_dirs.DiagnosticsPath, "machine-report.json");
                await File.WriteAllTextAsync(reportPath, json, stoppingToken);
                _logger.LogInformation("Machine report written to {Path}", reportPath);

                _lifetime.StopApplication();
                return;
            }

            // Check for diagnostics command
            if (Environment.GetCommandLineArgs().Contains("diagnostics", StringComparer.OrdinalIgnoreCase))
            {
                var exportPath = await _diagnosticsExporter.ExportAsync(stoppingToken);
                _logger.LogInformation("Diagnostics exported to {Path}", exportPath);
                Console.WriteLine($"Diagnostics exported to: {exportPath}");

                _lifetime.StopApplication();
                return;
            }

            // Check for cache status command
            var cliArgs = Environment.GetCommandLineArgs();
            if (cliArgs.Contains("cache", StringComparer.OrdinalIgnoreCase) && cliArgs.Contains("status", StringComparer.OrdinalIgnoreCase))
            {
                var status = await _cacheManager.GetStatusAsync(stoppingToken);
                var statusJson = JsonSerializer.Serialize(status, JsonOpts);
                Console.WriteLine(statusJson);
                _lifetime.StopApplication();
                return;
            }

            // Check for cache cleanup command
            if (cliArgs.Contains("cache", StringComparer.OrdinalIgnoreCase) && cliArgs.Contains("cleanup", StringComparer.OrdinalIgnoreCase))
            {
                var freed = await _cacheManager.CleanupAsync(ct: stoppingToken);
                Console.WriteLine($"Cache cleanup freed {freed} MB");
                _lifetime.StopApplication();
                return;
            }

            // portal status — estado do registro, sem expor segredos
            if (cliArgs.Contains("portal", StringComparer.OrdinalIgnoreCase) &&
                cliArgs.Contains("status", StringComparer.OrdinalIgnoreCase))
            {
                var currentIdentity = await _identityService.GetIdentityAsync(stoppingToken);
                var metadata = await _credentialStore.GetMetadataAsync(stoppingToken);

                var portalStatus = new
                {
                    registered = currentIdentity?.IsRegistered ?? false,
                    agent_id = currentIdentity?.AgentId,
                    installation_id = currentIdentity?.InstallationId,
                    registered_at_utc = currentIdentity?.RegisteredAtUtc,
                    credential = metadata is null
                        ? null
                        : new
                        {
                            type = metadata.Type,
                            fingerprint = metadata.Fingerprint,
                            stored_at_utc = metadata.StoredAtUtc,
                            expires_at_utc = metadata.ExpiresAtUtc,
                            last_used_at_utc = metadata.LastUsedAtUtc,
                            revoked = metadata.IsRevoked
                        },
                    protection = new
                    {
                        mechanism = _credentialProtector.MechanismName,
                        hardened = _credentialProtector.IsHardened
                    },
                    // Snapshot em memória do processo atual — como todos os hosted
                    // services do Agent iniciam junto com o host, este comando reflete
                    // o estado real de conexão do momento em que rodou, não um valor
                    // congelado. Não existe canal para controlar remotamente um Agent
                    // já em execução como serviço Windows a partir de uma segunda
                    // invocação de CLI; esse comando é para diagnóstico local.
                    connection = _connectionManager.GetStatus()
                };

                Console.WriteLine(JsonSerializer.Serialize(portalStatus, JsonOpts));
                _lifetime.StopApplication();
                return;
            }

            // portal connection-events — histórico recente de transições da conexão
            // WebSocket, persistido em connection_events (sobrevive a reinícios).
            if (cliArgs.Contains("portal", StringComparer.OrdinalIgnoreCase) &&
                cliArgs.Contains("connection-events", StringComparer.OrdinalIgnoreCase))
            {
                var events = await _connectionStateRepo.GetRecentEventsAsync(50, stoppingToken);
                Console.WriteLine(JsonSerializer.Serialize(events, JsonOpts));
                _lifetime.StopApplication();
                return;
            }

            // portal register — força novo registro (uso administrativo)
            if (cliArgs.Contains("portal", StringComparer.OrdinalIgnoreCase) &&
                cliArgs.Contains("register", StringComparer.OrdinalIgnoreCase))
            {
                var forced = await _registration.ForceRegisterAsync(stoppingToken);
                Console.WriteLine(JsonSerializer.Serialize(new
                {
                    outcome = forced.Outcome.ToString(),
                    agent_id = forced.AgentId,
                    reason_code = forced.ReasonCode,
                    message = forced.Message,
                    retryable = forced.Retryable
                }, JsonOpts));

                _lifetime.StopApplication();
                return;
            }

            // Check for execution list command
            if (cliArgs.Contains("execution", StringComparer.OrdinalIgnoreCase) && cliArgs.Contains("list", StringComparer.OrdinalIgnoreCase))
            {
                var active = await _executionManager.GetActiveExecutionsAsync(stoppingToken);
                var activeJson = JsonSerializer.Serialize(active, JsonOpts);
                Console.WriteLine(activeJson);
                _lifetime.StopApplication();
                return;
            }

            // Main loop — keep alive until stopped
            while (!stoppingToken.IsCancellationRequested)
            {
                await Task.Delay(TimeSpan.FromSeconds(30), stoppingToken);
            }
        }
        catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
        {
            // Normal shutdown
        }
        catch (Exception ex)
        {
            _logger.LogCritical(ex, "Fatal error in agent worker");
            try
            {
                await _stateManager.TransitionToAsync(AgentState.Faulted, ex.Message, source: "agent_worker", ct: CancellationToken.None);
            }
            catch { /* best effort */ }
        }
    }

    public override async Task StopAsync(CancellationToken cancellationToken)
    {
        _logger.LogInformation("Agent shutting down...");

        try
        {
            if (_stateManager.CurrentState is not (AgentState.Stopped or AgentState.Faulted or AgentState.Starting))
            {
                await _stateManager.TransitionToAsync(AgentState.Stopping, "Graceful shutdown", source: "agent_worker", ct: cancellationToken);
                await _stateManager.TransitionToAsync(AgentState.Stopped, "Shutdown complete", source: "agent_worker", ct: cancellationToken);
            }
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Error during state transition on shutdown");
        }

        await base.StopAsync(cancellationToken);
        _logger.LogInformation("Agent stopped");
    }

    private async Task TransitionToFaulted(string reason, CancellationToken ct)
    {
        try
        {
            await _stateManager.TransitionToAsync(AgentState.Faulted, reason, source: "agent_worker", ct: ct);
        }
        catch { /* best effort */ }
        _lifetime.StopApplication();
    }
}
