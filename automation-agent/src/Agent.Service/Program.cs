using Biason.AutomationAgent.Application.Diagnostics;
using Biason.AutomationAgent.Application.HealthChecks;
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

var builder = Host.CreateApplicationBuilder(args);

// === Configuration ===
builder.Configuration
    .AddJsonFile("appsettings.json", optional: true, reloadOnChange: true)
    .AddJsonFile($"appsettings.{builder.Environment.EnvironmentName}.json", optional: true)
    .AddEnvironmentVariables("AUTOMATION_AGENT_");

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

builder.Services.AddOptions<SecurityOptions>()
    .Bind(builder.Configuration.GetSection(SecurityOptions.Section));

// === Serilog ===
builder.Services.AddSerilog((services, loggerConfig) =>
{
    var dirs = services.GetRequiredService<IDirectoryResolver>();
    var loggingOpts = services.GetRequiredService<IOptions<LoggingOptions>>().Value;

    loggerConfig
        .MinimumLevel.Information()
        .Enrich.FromLogContext()
        .Enrich.WithProperty("Application", "BiasonAutomationAgent")
        .WriteTo.File(
            new CompactJsonFormatter(),
            Path.Combine(dirs.LogsPath, "agent-.log"),
            rollingInterval: RollingInterval.Day,
            fileSizeLimitBytes: loggingOpts.MaxFileSizeMb * 1024 * 1024,
            retainedFileCountLimit: loggingOpts.RetainedFileCountLimit,
            shared: true);

    if (builder.Environment.IsDevelopment())
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

// Execution infrastructure
builder.Services.AddSingleton<IWorkspaceManager, Biason.AutomationAgent.Application.Execution.WorkspaceManager>();
builder.Services.AddSingleton<Biason.AutomationAgent.Windows.Process.JobObjectManager>();
builder.Services.AddSingleton<IProcessManager, Biason.AutomationAgent.Windows.Process.ProcessTreeManager>();

// Windows collectors
builder.Services.AddSingleton<IOsInfoCollector>(sp =>
    new WindowsOsInfoCollector(sp.GetRequiredService<ILogger<WindowsOsInfoCollector>>(),
        sp.GetRequiredService<IOptions<AgentOptions>>().Value.Version));
builder.Services.AddSingleton<ICpuInfoCollector, WindowsCpuInfoCollector>();
builder.Services.AddSingleton<IMemoryInfoCollector, WindowsMemoryInfoCollector>();
builder.Services.AddSingleton<IDiskInfoCollector, WindowsDiskInfoCollector>();
builder.Services.AddSingleton<ISessionInfoCollector, WindowsSessionInfoCollector>();
builder.Services.AddSingleton<ISoftwareDetector, WindowsSoftwareDetector>();
builder.Services.AddSingleton<ICapabilityDetector, WindowsCapabilityDetector>();
builder.Services.AddSingleton<ICpuUsageProvider, WindowsCpuUsageCollector>();

// Application services
builder.Services.AddSingleton<IMachineProfiler, MachineProfilerService>();
builder.Services.AddSingleton<HealthCheckRunner>();
builder.Services.AddSingleton<MachineReportGenerator>();
builder.Services.AddSingleton<DiagnosticsExporter>();

// Resource monitor (background service)
builder.Services.AddSingleton<ResourceMonitorService>();
builder.Services.AddSingleton<IResourceMonitor>(sp => sp.GetRequiredService<ResourceMonitorService>());
builder.Services.AddHostedService(sp => sp.GetRequiredService<ResourceMonitorService>());

// Agent worker (main background service)
builder.Services.AddHostedService<AgentWorker>();

var host = builder.Build();
await host.RunAsync();
