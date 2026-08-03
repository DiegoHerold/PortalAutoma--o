using Biason.AutomationAgent.Application.Connection;
using Biason.AutomationAgent.Application.Heartbeat;
using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models;
using Biason.AutomationAgent.Domain.Models.Capacity;
using Biason.AutomationAgent.Domain.Models.Execution;
using Biason.AutomationAgent.IntegrationTests.Helpers;
using Biason.AutomationAgent.Protocol.Envelope;
using Biason.AutomationAgent.Protocol.Messages;
using Biason.AutomationAgent.Protocol.Serialization;
using FluentAssertions;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.Extensions.Options;
using NSubstitute;
using Xunit;

namespace Biason.AutomationAgent.IntegrationTests.Connection;

/// <summary>
/// Cobre <c>agent.heartbeat</c> (seção 16): envio periódico via a conexão persistente e
/// rastreamento do <c>agent.heartbeat_ack</c> correspondente.
/// </summary>
public sealed class HeartbeatServiceTests : IAsyncLifetime
{
    private readonly TestHelper _helper = new();

    public async Task InitializeAsync()
    {
        await _helper.InitializeDatabaseAsync();
        await _helper.SeedRegisteredAgentAsync(agentId: "agt_hb", credentialValue: "segredo-hb");
    }

    public Task DisposeAsync()
    {
        _helper.Dispose();
        return Task.CompletedTask;
    }

    private static PortalOptions FastHeartbeatOptions() => new()
    {
        Enabled = true,
        ApiBaseUrl = "https://portal.example/api",
        WebSocketUrl = "wss://portal.example/agents/connect",
        ConnectionTimeoutSeconds = 10,
        HeartbeatIntervalSeconds = 5, // mínimo permitido por [Range(5,300)]; o teste força o 1º envio manualmente
        ReconnectInitialSeconds = 1,
        ReconnectMaximumSeconds = 5
    };

    private HeartbeatSnapshotBuilder CreateSnapshotBuilder()
    {
        var stateManager = Substitute.For<IAgentStateManager>();
        stateManager.CurrentState.Returns(AgentState.Ready);

        var capacity = Substitute.For<ICapacityManager>();
        capacity.GetSnapshot().Returns(new CapacitySnapshot
        {
            AgentId = "agt_hb",
            AgentInstanceId = "inst_hb",
            ObservedAt = _helper.Clock.UtcNow,
            Pools = new Dictionary<PoolType, PoolCapacity>()
        });

        var resourceMonitor = Substitute.For<IResourceMonitor>();
        resourceMonitor.GetMetricsAsync(Arg.Any<CancellationToken>())
            .Returns(new ResourceMetrics { Current = null });

        var executionManager = Substitute.For<IExecutionManager>();
        executionManager.GetActiveExecutionsAsync(Arg.Any<CancellationToken>())
            .Returns(Array.Empty<ExecutionRecord>());

        var profileRepo = Substitute.For<IMachineProfileRepository>();
        profileRepo.GetLatestAsync(Arg.Any<CancellationToken>())
            .Returns((MachineProfileSnapshot?)null);

        return new HeartbeatSnapshotBuilder(
            _helper.CreateIdentityRepository(),
            stateManager,
            capacity,
            resourceMonitor,
            executionManager,
            profileRepo,
            Options.Create(new AgentOptions { Version = "0.3.0", Profile = "workstation" }));
    }

    private static async Task WaitUntilAsync(Func<bool> condition, TimeSpan timeout)
    {
        var deadline = DateTime.UtcNow + timeout;
        while (DateTime.UtcNow < deadline)
        {
            if (condition()) return;
            await Task.Delay(20);
        }

        condition().Should().BeTrue("condição não foi atingida dentro do tempo limite de teste");
    }

    // === heartbeat ===

    [Fact]
    public async Task HeartbeatService_SendsHeartbeatPayload_OnceConnected()
    {
        var factory = new FakeWebSocketTransportFactory();
        var identity = _helper.CreateIdentityRepository();
        var store = _helper.CreateCredentialStore();
        var connRepo = _helper.CreateConnectionRepository(identity);

        await using var connection = new PortalConnectionManager(
            factory, identity, store, connRepo, _helper.Clock,
            Options.Create(FastHeartbeatOptions()), NullLogger<PortalConnectionManager>.Instance);

        using var heartbeat = new HeartbeatService(
            connection, CreateSnapshotBuilder(), _helper.Clock,
            Options.Create(FastHeartbeatOptions()), NullLogger<HeartbeatService>.Instance);

        using var cts = new CancellationTokenSource();
        var runTask = connection.RunAsync(cts.Token);
        await WaitUntilAsync(() => connection.CurrentState == ConnectionState.Connected, TimeSpan.FromSeconds(5));

        await heartbeat.StartAsync(cts.Token);

        var transport = factory.Created[0];
        await WaitUntilAsync(() => transport.SentMessages.Count > 0, TimeSpan.FromSeconds(5));

        var raw = transport.SentMessages.First();
        var envelope = ProtocolJson.Deserialize<ProtocolEnvelope>(raw);

        envelope!.MessageType.Should().Be(PortalMessageTypes.Heartbeat);
        envelope.AgentId.Should().Be("agt_hb");

        heartbeat.LastSentAtUtc.Should().NotBeNull();

        await heartbeat.StopAsync(CancellationToken.None);
        cts.Cancel();
        try { await runTask; } catch (OperationCanceledException) { }
    }

    [Fact]
    public async Task HeartbeatAck_FromPortal_UpdatesLastAckTimestamp()
    {
        var factory = new FakeWebSocketTransportFactory();
        var identity = _helper.CreateIdentityRepository();
        var store = _helper.CreateCredentialStore();
        var connRepo = _helper.CreateConnectionRepository(identity);

        await using var connection = new PortalConnectionManager(
            factory, identity, store, connRepo, _helper.Clock,
            Options.Create(FastHeartbeatOptions()), NullLogger<PortalConnectionManager>.Instance);

        using var heartbeat = new HeartbeatService(
            connection, CreateSnapshotBuilder(), _helper.Clock,
            Options.Create(FastHeartbeatOptions()), NullLogger<HeartbeatService>.Instance);

        using var cts = new CancellationTokenSource();
        var runTask = connection.RunAsync(cts.Token);
        await WaitUntilAsync(() => connection.CurrentState == ConnectionState.Connected, TimeSpan.FromSeconds(5));

        heartbeat.LastAckAtUtc.Should().BeNull();

        // Simula o Portal respondendo ao heartbeat com agent.heartbeat_ack.
        var ackEnvelope = ProtocolEnvelope.Create(
            PortalMessageTypes.HeartbeatAck,
            payload: new { },
            agentId: "agt_hb",
            sentAtUtc: _helper.Clock.UtcNow);

        factory.Created[0].EnqueueInboundText(ProtocolJson.Serialize(ackEnvelope));

        await WaitUntilAsync(() => heartbeat.LastAckAtUtc is not null, TimeSpan.FromSeconds(5));

        heartbeat.LastAckAtUtc.Should().NotBeNull();

        cts.Cancel();
        try { await runTask; } catch (OperationCanceledException) { }
    }
}
