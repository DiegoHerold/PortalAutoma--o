using Biason.AutomationAgent.Domain.Agents;
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

    public PortalConnectionRepository CreateConnectionRepository(IAgentIdentityService identity)
    {
        return new PortalConnectionRepository(DbManager, identity);
    }

    public OutboxRepository CreateOutboxRepository()
    {
        return new OutboxRepository(DbManager);
    }

    public InboxRepository CreateInboxRepository()
    {
        return new InboxRepository(DbManager);
    }

    public ReservationRepository CreateReservationRepository()
    {
        return new ReservationRepository(DbManager);
    }

    public MessageAcknowledgementRepository CreateAcknowledgementRepository()
    {
        return new MessageAcknowledgementRepository(DbManager);
    }

    public SessionRunnerRepository CreateSessionRunnerRepository()
    {
        return new SessionRunnerRepository(DbManager);
    }

    public InteractiveSessionRepository CreateInteractiveSessionRepository()
    {
        return new InteractiveSessionRepository(DbManager);
    }

    public SessionEventRepository CreateSessionEventRepository()
    {
        return new SessionEventRepository(DbManager);
    }

    public SessionRunnerConnectionRepository CreateSessionRunnerConnectionRepository()
    {
        return new SessionRunnerConnectionRepository(DbManager);
    }

    public DesktopLockRepository CreateDesktopLockRepository()
    {
        return new DesktopLockRepository(DbManager);
    }

    public InteractiveExecutionAssignmentRepository CreateInteractiveExecutionAssignmentRepository()
    {
        return new InteractiveExecutionAssignmentRepository(DbManager);
    }

    public InteractiveExecutionProcessRepository CreateInteractiveExecutionProcessRepository()
    {
        return new InteractiveExecutionProcessRepository(DbManager);
    }

    public InteractiveExecutionScreenshotRepository CreateInteractiveExecutionScreenshotRepository()
    {
        return new InteractiveExecutionScreenshotRepository(DbManager);
    }

    public ApplicationProcessOwnershipRepository CreateApplicationProcessOwnershipRepository()
    {
        return new ApplicationProcessOwnershipRepository(DbManager);
    }

    /// <summary>
    /// Atalho para testes que precisam de um Agent já registrado (agent_id + credencial
    /// salvos), sem passar pelo fluxo completo de <c>AgentRegistrationService</c>.
    /// </summary>
    public async Task<(AgentIdentityRepository Identity, Biason.AutomationAgent.Infrastructure.Credentials.AgentCredentialStore Store)>
        SeedRegisteredAgentAsync(string agentId = "agt_teste", string credentialValue = "segredo-teste")
    {
        var identity = CreateIdentityRepository();
        await identity.GetOrCreateIdentityAsync();
        await identity.UpdateAgentIdAsync(agentId);

        var store = CreateCredentialStore();
        await store.SaveAsync(new AgentCredential
        {
            Type = "client_token",
            Value = credentialValue,
            ExpiresAtUtc = Clock.UtcNow.AddDays(90),
            StoredAtUtc = Clock.UtcNow
        });

        return (identity, store);
    }

    /// <summary>
    /// Protetor de credenciais isolado por teste. Usa o fallback AES para que
    /// a suíte rode igual em Windows e em CI Linux.
    /// </summary>
    public ICredentialProtector CreateCredentialProtector()
    {
        return new Biason.AutomationAgent.Infrastructure.Credentials.AesFileKeyCredentialProtector(
            Path.Combine(TempDir, "credential.key"));
    }

    public Biason.AutomationAgent.Infrastructure.Credentials.AgentCredentialStore CreateCredentialStore(
        ICredentialProtector? protector = null)
    {
        return new Biason.AutomationAgent.Infrastructure.Credentials.AgentCredentialStore(
            DbManager,
            protector ?? CreateCredentialProtector(),
            Clock,
            NullLogger<Biason.AutomationAgent.Infrastructure.Credentials.AgentCredentialStore>.Instance);
    }

    public void Dispose()
    {
        DbManager.Dispose();
        try { Directory.Delete(TempDir, recursive: true); } catch { /* best effort */ }
    }
}
