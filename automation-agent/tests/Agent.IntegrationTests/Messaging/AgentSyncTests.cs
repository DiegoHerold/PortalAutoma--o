using Biason.AutomationAgent.Application.Messaging;
using Biason.AutomationAgent.Application.Messaging.Handlers;
using Biason.AutomationAgent.Application.Sync;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models;
using Biason.AutomationAgent.Domain.Models.Capacity;
using Biason.AutomationAgent.Domain.Models.Execution;
using Biason.AutomationAgent.Domain.Models.Messaging;
using Biason.AutomationAgent.Infrastructure.Persistence;
using Biason.AutomationAgent.IntegrationTests.Helpers;
using Biason.AutomationAgent.Protocol.Messages;
using Biason.AutomationAgent.Protocol.Serialization;
using FluentAssertions;
using Microsoft.Extensions.Logging.Abstractions;
using NSubstitute;
using Xunit;

namespace Biason.AutomationAgent.IntegrationTests.Messaging;

public sealed class AgentSyncTests : IAsyncLifetime
{
    private readonly TestHelper _helper = new();

    public async Task InitializeAsync()
    {
        await _helper.InitializeDatabaseAsync();
        await _helper.SeedRegisteredAgentAsync(agentId: "agt_sync", credentialValue: "segredo-teste");
    }

    public Task DisposeAsync()
    {
        _helper.Dispose();
        return Task.CompletedTask;
    }

    [Fact]
    public async Task SyncRequest_EnqueuesSyncState_WithExecutionsReservationsLeasesAndArtifacts()
    {
        var executionRepo = new ExecutionRepository(_helper.DbManager);
        var reservationRepo = new ReservationRepository(_helper.DbManager);
        var leaseRepo = new ExecutionLeaseRepository(_helper.DbManager);
        var artifactRepo = new PendingArtifactRepository(_helper.DbManager);
        var syncRunRepo = new SyncRunRepository(_helper.DbManager);
        var outboxRepo = _helper.CreateOutboxRepository();
        var inboxRepo = _helper.CreateInboxRepository();
        var clock = _helper.Clock;

        await executionRepo.SaveAsync(new ExecutionRecord
        {
            ExecutionId = "exec_sync_1",
            CurrentState = ExecutionState.Running,
            CreatedAtUtc = clock.UtcNow,
            LastTransitionUtc = clock.UtcNow,
            AutomationId = "test.automation",
            AutomationVersionId = "pkg_test",
            Pool = PoolType.Background,
            CurrentAttemptId = "att_sync_1",
            ReservationId = "res_sync_1"
        });

        await reservationRepo.SaveAsync(new ResourceReservation
        {
            ReservationId = "res_sync_1",
            ExecutionId = "exec_sync_1",
            Pool = PoolType.Background,
            Slots = 1,
            Status = ReservationStatus.Committed,
            CreatedAtUtc = clock.UtcNow,
            ExpiresAtUtc = clock.UtcNow.AddMinutes(5)
        });

        await leaseRepo.SaveAsync(new ExecutionLeaseRecord
        {
            LeaseId = "lease_sync_1",
            ExecutionId = "exec_sync_1",
            ExecutionAttemptId = "att_sync_1",
            State = LeaseState.Active,
            GrantedAtUtc = clock.UtcNow,
            ExpiresAtUtc = clock.UtcNow.AddMinutes(5),
            LastRenewedAtUtc = clock.UtcNow
        });

        await artifactRepo.SaveAsync(new PendingArtifactRecord
        {
            ArtifactId = "art_sync_1",
            ExecutionId = "exec_sync_1",
            ExecutionAttemptId = "att_sync_1",
            Name = "report.txt",
            ContentType = "text/plain",
            SizeBytes = 12,
            Sha256 = "abc",
            LocalPath = Path.Combine(_helper.TempDir, "report.txt"),
            Status = ArtifactStatus.Pending,
            CreatedAtUtc = clock.UtcNow,
            AvailableAtUtc = clock.UtcNow
        });

        var stateManager = Substitute.For<IAgentStateManager>();
        stateManager.CurrentState.Returns(AgentState.Ready);

        var syncService = new AgentSyncService(
            _helper.CreateIdentityRepository(),
            stateManager,
            executionRepo,
            reservationRepo,
            leaseRepo,
            outboxRepo,
            inboxRepo,
            artifactRepo,
            syncRunRepo,
            new OutboxMessagePublisher(outboxRepo, _helper.CreateIdentityRepository(), clock),
            clock,
            NullLogger<AgentSyncService>.Instance);

        var handler = new AgentSyncRequestHandler(syncService);
        var command = new InboxCommand
        {
            Id = 1,
            MessageId = "msg_sync_request_1",
            CommandType = PortalMessageTypes.SyncRequest,
            PayloadJson = "{}",
            ReceivedAtUtc = clock.UtcNow,
            Status = InboxCommandStatus.Processing
        };

        var result = await handler.HandleAsync(command);

        result.Success.Should().BeTrue();
        result.Result.Should().Be("sync_state_enqueued");

        var outbox = await outboxRepo.GetReadyBatchAsync(10, clock.UtcNow.AddMinutes(1));
        var syncMessage = outbox.Should().ContainSingle(m => m.MessageType == PortalMessageTypes.SyncState).Which;
        var payload = ProtocolJson.Deserialize<AgentSyncStatePayload>(syncMessage.PayloadJson);

        payload!.AgentId.Should().Be("agt_sync");
        payload.AgentState.Should().Be(nameof(AgentState.Ready));
        payload.RunningExecutions.Should().ContainSingle(e => e.ExecutionId == "exec_sync_1");
        payload.Reservations.Should().ContainSingle(r => r.ReservationId == "res_sync_1");
        payload.Leases.Should().ContainSingle(l => l.LeaseId == "lease_sync_1");
        payload.PendingArtifacts.Should().ContainSingle(a => a.ArtifactId == "art_sync_1");
        payload.Reconciliation.Should().ContainSingle(r => r.Result == ExecutionReconciliationResult.InSync);

        var latestSync = await syncRunRepo.GetLatestAsync();
        latestSync!.Status.Should().Be("completed");
        latestSync.RunningExecutionsReported.Should().Be(1);
    }
}
