using Biason.AutomationAgent.Application.Diagnostics;
using Biason.AutomationAgent.Application.HealthChecks;
using Biason.AutomationAgent.Application.Interactive;
using Biason.AutomationAgent.Application.Sessions;
using Biason.AutomationAgent.Application.Services;
using Biason.AutomationAgent.Application.Validation;
using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Infrastructure.Clock;
using Biason.AutomationAgent.Infrastructure.Database;
using Biason.AutomationAgent.Infrastructure.Persistence;
using Biason.AutomationAgent.Infrastructure.Storage;
using Biason.AutomationAgent.Service;
using Biason.AutomationAgent.Windows.Collectors;
using Biason.AutomationAgent.Windows.Detection;
using Microsoft.Extensions.Options;
using Serilog;
using Serilog.Formatting.Compact;

if (await EarlySessionCli.TryHandleAsync(args, CancellationToken.None))
    return;

CertificationStartupTrace.Write("program.start");
var builder = Host.CreateApplicationBuilder(args);
CertificationStartupTrace.Write("builder.created");

// === Configuration ===
builder.Configuration
    .AddJsonFile("appsettings.json", optional: true, reloadOnChange: true)
    .AddJsonFile($"appsettings.{builder.Environment.EnvironmentName}.json", optional: true)
    .AddEnvironmentVariables("AUTOMATION_AGENT_");
CertificationStartupTrace.Write("configuration.loaded");

builder.Services.AddOptions<AgentOptions>()
    .Bind(builder.Configuration.GetSection(AgentOptions.Section))
    .ValidateDataAnnotations()
    .ValidateOnStart();

builder.Services.AddOptions<StorageOptions>()
    .Bind(builder.Configuration.GetSection(StorageOptions.Section))
    .ValidateDataAnnotations()
    .ValidateOnStart();

builder.Services.AddOptions<MonitoringOptions>()
    .Bind(builder.Configuration.GetSection(MonitoringOptions.Section))
    .ValidateDataAnnotations()
    .ValidateOnStart();

builder.Services.AddOptions<MachineProfilerOptions>()
    .Bind(builder.Configuration.GetSection(MachineProfilerOptions.Section))
    .ValidateDataAnnotations()
    .ValidateOnStart();

builder.Services.AddOptions<DatabaseOptions>()
    .Bind(builder.Configuration.GetSection(DatabaseOptions.Section))
    .ValidateOnStart();

builder.Services.AddOptions<LoggingOptions>()
    .Bind(builder.Configuration.GetSection(LoggingOptions.Section))
    .ValidateOnStart();

builder.Services.AddOptions<DevelopmentOptions>()
    .Bind(builder.Configuration.GetSection(DevelopmentOptions.Section));

builder.Services.AddOptions<ExecutionOptions>()
    .Bind(builder.Configuration.GetSection(ExecutionOptions.Section))
    .ValidateDataAnnotations()
    .ValidateOnStart();

builder.Services.AddOptions<CapacityOptions>()
    .Bind(builder.Configuration.GetSection(CapacityOptions.Section))
    .ValidateDataAnnotations()
    .ValidateOnStart();

builder.Services.AddOptions<DownloadOptions>()
    .Bind(builder.Configuration.GetSection(DownloadOptions.Section))
    .ValidateDataAnnotations()
    .ValidateOnStart();

builder.Services.AddOptions<MessagingOptions>()
    .Bind(builder.Configuration.GetSection(MessagingOptions.Section))
    .ValidateDataAnnotations()
    .ValidateOnStart();

builder.Services.AddOptions<SessionRunnerOptions>()
    .Bind(builder.Configuration.GetSection(SessionRunnerOptions.Section))
    .ValidateDataAnnotations()
    .ValidateOnStart();

builder.Services.AddOptions<InteractiveSessionsOptions>()
    .Bind(builder.Configuration.GetSection(InteractiveSessionsOptions.Section))
    .ValidateDataAnnotations()
    .ValidateOnStart();

builder.Services.AddOptions<InteractivePoolOptions>()
    .Bind(builder.Configuration.GetSection(InteractivePoolOptions.Section))
    .ValidateDataAnnotations()
    .ValidateOnStart();

builder.Services.AddOptions<InteractiveExecutionOptions>()
    .Bind(builder.Configuration.GetSection(InteractiveExecutionOptions.Section))
    .ValidateDataAnnotations()
    .ValidateOnStart();

builder.Services.AddOptions<ScreenshotOptions>()
    .Bind(builder.Configuration.GetSection(ScreenshotOptions.Section))
    .ValidateDataAnnotations()
    .ValidateOnStart();

builder.Services.AddOptions<LocalProtocolOptions>()
    .Bind(builder.Configuration.GetSection(LocalProtocolOptions.Section))
    .ValidateDataAnnotations()
    .ValidateOnStart();

builder.Services.AddOptions<SecurityOptions>()
    .Bind(builder.Configuration.GetSection(SecurityOptions.Section));

// === Fase 3 — Portal ===
builder.Services.AddOptions<PortalOptions>()
    .Bind(builder.Configuration.GetSection(PortalOptions.Section))
    .ValidateDataAnnotations()
    .ValidateOnStart();

// === Serilog ===
var bootstrapLoggingOptions = new LoggingOptions();
builder.Configuration.GetSection(LoggingOptions.Section).Bind(bootstrapLoggingOptions);
var bootstrapDevelopmentOptions = new DevelopmentOptions();
builder.Configuration.GetSection(DevelopmentOptions.Section).Bind(bootstrapDevelopmentOptions);
var bootstrapDataDirectory = bootstrapDevelopmentOptions.DataDirectory
    ?? Environment.GetEnvironmentVariable("AUTOMATION_AGENT_DATA_DIR")
    ?? @"C:\ProgramData\BiasonAutomationAgent";
var bootstrapLogsPath = Path.Combine(bootstrapDataDirectory, "logs");
Directory.CreateDirectory(bootstrapLogsPath);

builder.Services.AddSerilog((_, loggerConfig) =>
{

    loggerConfig
        .MinimumLevel.Information()
        .Enrich.FromLogContext()
        .Enrich.WithProperty("Application", "BiasonAutomationAgent")
        .WriteTo.File(
            new CompactJsonFormatter(),
            Path.Combine(bootstrapLogsPath, "agent-.log"),
            rollingInterval: RollingInterval.Day,
            fileSizeLimitBytes: bootstrapLoggingOptions.MaxFileSizeMb * 1024 * 1024,
            retainedFileCountLimit: bootstrapLoggingOptions.RetainedFileCountLimit,
            shared: true);

    if (builder.Environment.IsDevelopment() || bootstrapDevelopmentOptions.ConsoleLogging)
    {
        loggerConfig.WriteTo.Console(outputTemplate:
            "[{Timestamp:HH:mm:ss} {Level:u3}] {SourceContext}: {Message:lj}{NewLine}{Exception}");
    }
});

// === Windows Service support ===
builder.Services.AddWindowsService(options =>
{
    options.ServiceName = "BiasonAutomationAgent";
});

// === Core services ===
builder.Services.AddSingleton<IClock, SystemClock>();

// Directory resolver
builder.Services.AddSingleton<IDirectoryResolver>(sp =>
{
    var logger = sp.GetRequiredService<ILogger<AgentDirectoryResolver>>();
    var devOpts = sp.GetRequiredService<IOptions<DevelopmentOptions>>().Value;
    return new AgentDirectoryResolver(logger, devOpts.DataDirectory);
});

// Database
builder.Services.AddSingleton<SqliteDatabaseManager>();
builder.Services.AddSingleton<IDatabaseManager>(sp => sp.GetRequiredService<SqliteDatabaseManager>());

// Identity
builder.Services.AddSingleton<AgentIdentityRepository>();
builder.Services.AddSingleton<IAgentIdentityService>(sp => sp.GetRequiredService<AgentIdentityRepository>());

// State management
builder.Services.AddSingleton<AgentStateManagerImpl>();
builder.Services.AddSingleton<IAgentStateManager>(sp => sp.GetRequiredService<AgentStateManagerImpl>());

// Repositories — Phase 1
builder.Services.AddSingleton<IResourceSampleRepository, ResourceSampleRepository>();
builder.Services.AddSingleton<ICapabilityRepository, CapabilityRepository>();
builder.Services.AddSingleton<IMachineProfileRepository, MachineProfileRepository>();
builder.Services.AddSingleton<IExecutionRepository, ExecutionRepository>();

// Repositories — Phase 2
builder.Services.AddSingleton<IRuntimeArtifactRepository, RuntimeArtifactRepository>();
builder.Services.AddSingleton<IPackageArtifactRepository, PackageArtifactRepository>();
builder.Services.AddSingleton<IExecutionAttemptRepository, ExecutionAttemptRepository>();
builder.Services.AddSingleton<IExecutionEventRepository, ExecutionEventRepository>();
builder.Services.AddSingleton<IReservationRepository, ReservationRepository>();

// Repositories — Bloco 5.5 (oferta/commit/lease do Portal)
builder.Services.AddSingleton<IExecutionOfferRepository, ExecutionOfferRepository>();
builder.Services.AddSingleton<IExecutionCommitRepository, ExecutionCommitRepository>();
builder.Services.AddSingleton<IExecutionLeaseRepository, ExecutionLeaseRepository>();
builder.Services.AddSingleton<IPendingArtifactRepository, PendingArtifactRepository>();
builder.Services.AddSingleton<ISyncRunRepository, SyncRunRepository>();

// Repositories — Phase 3 durable messaging
builder.Services.AddSingleton<IOutboxRepository, OutboxRepository>();
builder.Services.AddSingleton<IInboxRepository, InboxRepository>();
builder.Services.AddSingleton<IMessageAcknowledgementRepository, MessageAcknowledgementRepository>();

// Repositories — local interactive sessions
builder.Services.AddSingleton<ISessionRunnerRepository, SessionRunnerRepository>();
builder.Services.AddSingleton<IInteractiveSessionRepository, InteractiveSessionRepository>();
builder.Services.AddSingleton<ISessionEventRepository, SessionEventRepository>();
builder.Services.AddSingleton<ISessionRunnerConnectionRepository, SessionRunnerConnectionRepository>();
builder.Services.AddSingleton<IDesktopLockRepository, DesktopLockRepository>();
builder.Services.AddSingleton<IInteractiveExecutionAssignmentRepository, InteractiveExecutionAssignmentRepository>();
builder.Services.AddSingleton<IInteractiveExecutionProcessRepository, InteractiveExecutionProcessRepository>();
builder.Services.AddSingleton<IInteractiveExecutionScreenshotRepository, InteractiveExecutionScreenshotRepository>();
builder.Services.AddSingleton<IApplicationProcessOwnershipRepository, ApplicationProcessOwnershipRepository>();

// Validation
builder.Services.AddSingleton<IManifestValidator, ManifestValidator>();

// Security and downloads
builder.Services.AddSingleton<IIntegrityVerifier, Biason.AutomationAgent.Infrastructure.Security.IntegrityVerifier>();
builder.Services.AddHttpClient<IDownloadManager, Biason.AutomationAgent.Infrastructure.Downloads.DownloadManager>();

// Stores (immutable)
builder.Services.AddSingleton<IRuntimeStore, Biason.AutomationAgent.Infrastructure.Stores.RuntimeStore>();
builder.Services.AddSingleton<IPackageStore, Biason.AutomationAgent.Infrastructure.Stores.PackageStore>();

// Capacity and admission
builder.Services.AddSingleton<ICapacityManager, Biason.AutomationAgent.Application.Capacity.CapacityManager>();
builder.Services.AddSingleton<IResourceReservationManager, Biason.AutomationAgent.Application.Capacity.ResourceReservationManager>();
builder.Services.AddSingleton<IAdmissionController, Biason.AutomationAgent.Application.Capacity.AdmissionController>();
builder.Services.AddHostedService<Biason.AutomationAgent.Application.Capacity.ReservationExpirationService>();

// Execution infrastructure
builder.Services.AddSingleton<IWorkspaceManager, Biason.AutomationAgent.Application.Execution.WorkspaceManager>();
builder.Services.AddSingleton<Biason.AutomationAgent.Windows.Process.JobObjectManager>();
builder.Services.AddSingleton<IProcessManager, Biason.AutomationAgent.Windows.Process.ProcessTreeManager>();

// Launchers
builder.Services.AddSingleton<ILauncher, Biason.AutomationAgent.Application.Launchers.PythonFunctionLauncher>();
builder.Services.AddSingleton<ILauncher, Biason.AutomationAgent.Application.Launchers.PythonModuleLauncher>();
builder.Services.AddSingleton<ILauncher, Biason.AutomationAgent.Application.Launchers.PowerShellLauncher>();
builder.Services.AddSingleton<ILauncher, Biason.AutomationAgent.Application.Launchers.ExecutableLauncher>();
builder.Services.AddSingleton<ILauncher, Biason.AutomationAgent.Application.Launchers.BrowserPlaywrightLauncher>();

// Execution orchestration
builder.Services.AddSingleton<ICancellationManager, Biason.AutomationAgent.Application.Execution.CancellationManager>();
builder.Services.AddSingleton<IResultCollector, Biason.AutomationAgent.Application.Execution.ResultCollector>();
builder.Services.AddSingleton<Biason.AutomationAgent.Application.Execution.StepImageRegistrar>();
builder.Services.AddSingleton<Biason.AutomationAgent.Application.Execution.ExecutionHostPipePump>();
builder.Services.AddSingleton<IExecutionManager, Biason.AutomationAgent.Application.Execution.ExecutionManager>();
builder.Services.AddSingleton<Biason.AutomationAgent.Application.Execution.ExecutionMetricsCollector>();
builder.Services.AddSingleton<ICacheManager, Biason.AutomationAgent.Application.Execution.CacheManager>();

// Leases de execução (Bloco 5.5, seção 9/19)
builder.Services.AddSingleton<Biason.AutomationAgent.Domain.Contracts.IExecutionLeaseManager,
    Biason.AutomationAgent.Application.Execution.ExecutionLeaseManager>();
builder.Services.AddHostedService<Biason.AutomationAgent.Application.Execution.LeaseRenewalService>();
builder.Services.AddHostedService<Biason.AutomationAgent.Application.Execution.LeaseMessageListenerService>();

// Sync e artifacts remotos (Bloco 5.5)
builder.Services.AddSingleton<IArtifactManager, Biason.AutomationAgent.Application.Artifacts.ArtifactManager>();
builder.Services.AddSingleton<Biason.AutomationAgent.Application.Artifacts.IArtifactAcknowledgementHandler,
    Biason.AutomationAgent.Application.Artifacts.ArtifactAcknowledgementHandler>();
builder.Services.AddSingleton<IArtifactUploadManager, Biason.AutomationAgent.Application.Artifacts.ArtifactUploadManager>();
builder.Services.AddHostedService<Biason.AutomationAgent.Application.Artifacts.ArtifactUploadService>();
builder.Services.AddSingleton<IAgentSyncService, Biason.AutomationAgent.Application.Sync.AgentSyncService>();
builder.Services.AddHostedService<Biason.AutomationAgent.Application.Sync.AgentSyncOnReconnectService>();

// Local interactive sessions and Session Runner
builder.Services.AddSingleton<ISessionRunnerRegistry, SessionRunnerRegistry>();
builder.Services.AddSingleton<IInteractiveExecutionTokenService, InteractiveExecutionTokenService>();
builder.Services.AddSingleton<IInteractiveSessionSelector, InteractiveSessionSelector>();
builder.Services.AddSingleton<ISessionCapabilityService, SessionCapabilityService>();
builder.Services.AddSingleton<IDesktopLockManager, DesktopLockManager>();
builder.Services.AddSingleton<IInteractivePoolService, InteractivePoolService>();
builder.Services.AddSingleton<IInteractiveExecutionCoordinator, InteractiveExecutionCoordinator>();
builder.Services.AddSingleton<SessionRunnerPipeServer>();
builder.Services.AddHostedService(sp => sp.GetRequiredService<SessionRunnerPipeServer>());
builder.Services.AddHostedService<WindowsSessionDiscoveryService>();

// Windows collectors
builder.Services.AddSingleton<IOsInfoCollector>(sp =>
    new WindowsOsInfoCollector(sp.GetRequiredService<ILogger<WindowsOsInfoCollector>>(),
        sp.GetRequiredService<IOptions<AgentOptions>>().Value.Version));
builder.Services.AddSingleton<ICpuInfoCollector, WindowsCpuInfoCollector>();
builder.Services.AddSingleton<IMemoryInfoCollector, WindowsMemoryInfoCollector>();
builder.Services.AddSingleton<IDiskInfoCollector, WindowsDiskInfoCollector>();
builder.Services.AddSingleton<IDesktopStateReader, WindowsDesktopStateReader>();
builder.Services.AddSingleton<IWindowsSessionDiscovery, WindowsSessionDiscovery>();
builder.Services.AddSingleton<ISessionInfoCollector, WindowsSessionInfoCollector>();
builder.Services.AddSingleton<ISoftwareDetector, WindowsSoftwareDetector>();
builder.Services.AddSingleton<ICapabilityDetector, WindowsCapabilityDetector>();
builder.Services.AddSingleton<ICpuUsageProvider, WindowsCpuUsageCollector>();
builder.Services.AddSingleton<ISessionRunnerProcessValidator, Biason.AutomationAgent.Windows.Process.WindowsSessionRunnerProcessValidator>();
builder.Services.AddSingleton<IApplicationProcessInspector, Biason.AutomationAgent.Windows.Process.WindowsApplicationProcessInspector>();

// === Fase 3 — Registro e credenciais ===
// A proteção da credencial é escolhida por plataforma: DPAPI no Windows,
// AES-GCM com chave em arquivo nos demais (apenas dev/CI).
builder.Services.AddSingleton<ICredentialProtector>(sp =>
    Biason.AutomationAgent.Infrastructure.Credentials.CredentialProtectorFactory.Create(
        sp.GetRequiredService<IDirectoryResolver>(),
        sp.GetRequiredService<ILoggerFactory>()));

builder.Services.AddSingleton<IAgentCredentialStore,
    Biason.AutomationAgent.Infrastructure.Credentials.AgentCredentialStore>();

builder.Services.AddHttpClient<IPortalApiClient,
    Biason.AutomationAgent.Infrastructure.Http.PortalApiClient>((sp, http) =>
{
    var portal = sp.GetRequiredService<IOptions<PortalOptions>>().Value;
    http.Timeout = TimeSpan.FromSeconds(portal.ConnectionTimeoutSeconds);
    http.DefaultRequestHeaders.UserAgent.ParseAdd(
        $"BiasonAutomationAgent/{sp.GetRequiredService<IOptions<AgentOptions>>().Value.Version}");
});

builder.Services.AddHttpClient<IArtifactContentUploader,
    Biason.AutomationAgent.Infrastructure.Http.ArtifactContentUploader>((sp, http) =>
{
    var execution = sp.GetRequiredService<IOptions<ExecutionOptions>>().Value;
    http.Timeout = TimeSpan.FromSeconds(execution.ArtifactUploadTimeoutSeconds);
    http.DefaultRequestHeaders.UserAgent.ParseAdd(
        $"BiasonAutomationAgent/{sp.GetRequiredService<IOptions<AgentOptions>>().Value.Version}");
});

builder.Services.AddSingleton<IAgentRegistrationService,
    Biason.AutomationAgent.Application.Registration.AgentRegistrationService>();

// === Fase 3 — Conexão WebSocket persistente e heartbeat ===
builder.Services.AddSingleton<IWebSocketTransportFactory,
    Biason.AutomationAgent.Infrastructure.WebSockets.ClientWebSocketTransportFactory>();

builder.Services.AddSingleton<IConnectionStateRepository, PortalConnectionRepository>();

builder.Services.AddSingleton<Biason.AutomationAgent.Application.Connection.PortalConnectionManager>();
builder.Services.AddSingleton<IPortalConnectionManager>(sp =>
    sp.GetRequiredService<Biason.AutomationAgent.Application.Connection.PortalConnectionManager>());
builder.Services.AddHostedService<Biason.AutomationAgent.Application.Connection.PortalConnectionHostedService>();

builder.Services.AddSingleton<Biason.AutomationAgent.Application.Heartbeat.HeartbeatSnapshotBuilder>();
builder.Services.AddSingleton<Biason.AutomationAgent.Application.Heartbeat.HeartbeatService>();
builder.Services.AddHostedService(sp =>
    sp.GetRequiredService<Biason.AutomationAgent.Application.Heartbeat.HeartbeatService>());

builder.Services.AddSingleton<Biason.AutomationAgent.Application.Messaging.OutboxMessagePublisher>();
builder.Services.AddSingleton<Biason.AutomationAgent.Application.Messaging.ExecutionAttemptSequenceTracker>();
builder.Services.AddSingleton<Biason.AutomationAgent.Application.Messaging.AgentInventoryPublisher>();
builder.Services.AddSingleton<Biason.AutomationAgent.Application.Execution.IExecutionLifecyclePublisher,
    Biason.AutomationAgent.Application.Messaging.OutboxExecutionLifecyclePublisher>();
builder.Services.AddSingleton<Biason.AutomationAgent.Application.Messaging.PortalInboxService>();
builder.Services.AddHostedService(sp =>
    sp.GetRequiredService<Biason.AutomationAgent.Application.Messaging.PortalInboxService>());
builder.Services.AddSingleton<Biason.AutomationAgent.Application.Messaging.PortalMessageAcknowledgementService>();
builder.Services.AddHostedService(sp =>
    sp.GetRequiredService<Biason.AutomationAgent.Application.Messaging.PortalMessageAcknowledgementService>());
builder.Services.AddHostedService<Biason.AutomationAgent.Application.Messaging.OutboxBatchSender>();
builder.Services.AddHostedService<Biason.AutomationAgent.Application.Messaging.InboxCommandProcessor>();

// === Bloco 5.5 — handlers de comando do Portal ===
// Sem isso, InboxCommandProcessor não tinha nenhum IInboxCommandHandler
// registrado e todo comando do Portal ficava pending indefinidamente.
builder.Services.AddSingleton<Biason.AutomationAgent.Application.Messaging.IInboxCommandHandler,
    Biason.AutomationAgent.Application.Messaging.Handlers.ExecutionOfferHandler>();
builder.Services.AddSingleton<Biason.AutomationAgent.Application.Messaging.IInboxCommandHandler,
    Biason.AutomationAgent.Application.Messaging.Handlers.ExecutionCommitHandler>();
builder.Services.AddSingleton<Biason.AutomationAgent.Application.Messaging.IInboxCommandHandler,
    Biason.AutomationAgent.Application.Messaging.Handlers.ExecutionCancelRequestedHandler>();
builder.Services.AddSingleton<Biason.AutomationAgent.Application.Messaging.IInboxCommandHandler,
    Biason.AutomationAgent.Application.Messaging.Handlers.AgentSyncRequestHandler>();
builder.Services.AddSingleton<Biason.AutomationAgent.Application.Messaging.IInboxCommandHandler,
    Biason.AutomationAgent.Application.Messaging.Handlers.ArtifactConfirmedHandler>();

// Application services
builder.Services.AddSingleton<IMachineProfiler, MachineProfilerService>();
builder.Services.AddSingleton<HealthCheckRunner>();
builder.Services.AddSingleton<MachineReportGenerator>();
builder.Services.AddSingleton<DiagnosticsExporter>();
builder.Services.AddSingleton<SessionCliHandler>();

// Resource monitor (background service)
builder.Services.AddSingleton<ResourceMonitorService>();
builder.Services.AddSingleton<IResourceMonitor>(sp => sp.GetRequiredService<ResourceMonitorService>());
builder.Services.AddHostedService(sp => sp.GetRequiredService<ResourceMonitorService>());

// Agent worker (main background service)
builder.Services.AddHostedService<AgentWorker>();

CertificationStartupTrace.Write("host.build.start");
using var host = builder.Build();
CertificationStartupTrace.Write("host.build.done");

CertificationStartupTrace.Write("host.preflight.start");
var startupDirs = host.Services.GetRequiredService<IDirectoryResolver>();
if (!startupDirs.Validate(out var startupErrors))
{
    Console.Error.WriteLine($"Directory validation failed: {string.Join("; ", startupErrors)}");
    Environment.ExitCode = 2;
    return;
}

startupDirs.EnsureDirectoriesExist();
await host.Services.GetRequiredService<SqliteDatabaseManager>().InitializeAsync();
CertificationStartupTrace.Write("host.preflight.done");

if (SessionCliHandler.IsSessionCommand(Environment.GetCommandLineArgs()))
{
    var dirs = host.Services.GetRequiredService<IDirectoryResolver>();
    if (!dirs.Validate(out var errors))
    {
        Console.Error.WriteLine($"Directory validation failed: {string.Join("; ", errors)}");
        Environment.ExitCode = 2;
        return;
    }

    dirs.EnsureDirectoriesExist();
    await host.Services.GetRequiredService<SqliteDatabaseManager>().InitializeAsync();

    var handled = await host.Services
        .GetRequiredService<SessionCliHandler>()
        .TryHandleAsync(Environment.GetCommandLineArgs(), CancellationToken.None);

    if (handled)
        return;
}

CertificationStartupTrace.Write("host.run.start");
await host.RunAsync();
CertificationStartupTrace.Write("host.run.done");
