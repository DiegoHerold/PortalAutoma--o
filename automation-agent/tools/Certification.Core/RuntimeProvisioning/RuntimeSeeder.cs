using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Models.Storage;
using Biason.AutomationAgent.Infrastructure.Clock;
using Biason.AutomationAgent.Infrastructure.Database;
using Biason.AutomationAgent.Infrastructure.Persistence;
using Biason.AutomationAgent.Infrastructure.Security;
using Biason.AutomationAgent.Infrastructure.Storage;
using Biason.AutomationAgent.Infrastructure.Stores;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;

namespace Biason.AutomationAgent.Certification.Core.RuntimeProvisioning;

/// <summary>
/// Preseeds a runtime into the certification Agent's own Runtime Store,
/// using the *real* store implementation
/// (Agent.Infrastructure/Stores/RuntimeStore.cs) — same hash verification,
/// same extraction, same SQLite artifact bookkeeping a Portal-triggered
/// download would produce. This exists because, unlike packages (which
/// Agent.Application/Messaging/Handlers/ExecutionOfferHandler.cs downloads
/// and imports on demand when an offer arrives), nothing in the current
/// Agent codebase downloads a *runtime* on demand — ExecutionManager just
/// throws "Runtime not found" if it is missing
/// (Agent.Application/Execution/ExecutionManager.cs). Until that gap is
/// closed, the runtime has to be preseeded before the first certification
/// execution (docs/certification-harness.md, "Known Gaps").
///
/// This is preseed, not production provisioning — see
/// docs/certification-harness.md item 24 for why, and for what a real
/// runtime archive needs to contain (a working `python.exe` at the archive
/// root for runtime.id "python-core").
/// </summary>
public static class RuntimeSeeder
{
    public static async Task<RuntimeArtifact> ImportRuntimeAsync(
        string agentDataDirectory,
        string runtimeId,
        string version,
        string archivePath,
        ILoggerFactory loggerFactory,
        CancellationToken ct = default)
    {
        if (!File.Exists(archivePath))
            throw new FileNotFoundException($"Runtime archive not found: {archivePath}", archivePath);

        var services = new ServiceCollection();
        services.AddSingleton(loggerFactory);
        services.AddLogging();
        services.AddOptions<DownloadOptions>();
        services.AddOptions<SecurityOptions>();
        services.AddOptions<DatabaseOptions>();

        services.AddSingleton<IClock, SystemClock>();
        services.AddSingleton<IDirectoryResolver>(sp =>
            new AgentDirectoryResolver(sp.GetRequiredService<ILogger<AgentDirectoryResolver>>(), agentDataDirectory));
        services.AddSingleton<SqliteDatabaseManager>();
        services.AddSingleton<IIntegrityVerifier, IntegrityVerifier>();
        services.AddSingleton<IRuntimeArtifactRepository, RuntimeArtifactRepository>();
        services.AddSingleton<IRuntimeStore, RuntimeStore>();

        await using var provider = services.BuildServiceProvider();

        var dirs = provider.GetRequiredService<IDirectoryResolver>();
        if (!dirs.Validate(out var errors))
            throw new InvalidOperationException($"Invalid certification data directory: {string.Join("; ", errors)}");
        dirs.EnsureDirectoriesExist();

        var db = provider.GetRequiredService<SqliteDatabaseManager>();
        await db.InitializeAsync(ct);

        var verifier = provider.GetRequiredService<IIntegrityVerifier>();
        // The "expected" hash is computed from the same file we are about
        // to import: for a local preseed there is no separate trusted
        // source declaring the hash up front (unlike a Portal-issued
        // download, where the expected hash comes from the catalog record).
        // RuntimeStore.ImportAsync still independently recomputes and
        // compares it, so this exercises the real verification path rather
        // than bypassing it.
        var computedSha256 = await verifier.ComputeSha256Async(archivePath, ct);

        var store = provider.GetRequiredService<IRuntimeStore>();
        return await store.ImportAsync(runtimeId, version, archivePath, computedSha256, ct);
    }

    public static bool IsRuntimeAvailable(string agentDataDirectory, string runtimeId, string version, ILoggerFactory loggerFactory)
    {
        var resolver = new AgentDirectoryResolver(loggerFactory.CreateLogger<AgentDirectoryResolver>(), agentDataDirectory);
        var storePath = Path.Combine(resolver.RuntimesPath, $"{runtimeId}-{version}");
        return Directory.Exists(storePath);
    }
}
