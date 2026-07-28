using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Infrastructure.Clock;
using Biason.AutomationAgent.Infrastructure.Database;
using Biason.AutomationAgent.Infrastructure.Persistence;
using Biason.AutomationAgent.Infrastructure.Storage;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.Extensions.Options;

namespace Biason.AutomationAgent.IntegrationTests.Helpers;

public sealed class TestHelper : IDisposable
{
    public string TempDir { get; }
    public IDirectoryResolver Dirs { get; }
    public SqliteDatabaseManager DbManager { get; }
    public IClock Clock { get; }

    public TestHelper()
    {
        TempDir = Path.Combine(Path.GetTempPath(), $"agent-itest-{Guid.NewGuid():N}");
        var logger = NullLogger<AgentDirectoryResolver>.Instance;
        Dirs = new AgentDirectoryResolver(logger, TempDir);
        Dirs.EnsureDirectoriesExist();

        Clock = new SystemClock();

        var dbOpts = Options.Create(new DatabaseOptions());
        var dbLogger = NullLogger<SqliteDatabaseManager>.Instance;
        DbManager = new SqliteDatabaseManager(Dirs, dbOpts, dbLogger);
    }

    public async Task InitializeDatabaseAsync()
    {
        await DbManager.InitializeAsync();
    }

    public AgentIdentityRepository CreateIdentityRepository()
    {
        return new AgentIdentityRepository(DbManager, Clock, NullLogger<AgentIdentityRepository>.Instance);
    }

    public AgentStateManagerImpl CreateStateManager()
    {
        return new AgentStateManagerImpl(DbManager, Clock, NullLogger<AgentStateManagerImpl>.Instance);
    }

    public ResourceSampleRepository CreateResourceSampleRepository()
    {
        return new ResourceSampleRepository(DbManager, NullLogger<ResourceSampleRepository>.Instance);
    }

    public CapabilityRepository CreateCapabilityRepository()
    {
        return new CapabilityRepository(DbManager);
    }

    public void Dispose()
    {
        DbManager.Dispose();
        try { Directory.Delete(TempDir, recursive: true); } catch { /* best effort */ }
    }
}
