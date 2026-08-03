using Biason.AutomationAgent.Application.Connection;
using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.IntegrationTests.Helpers;
using FluentAssertions;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.Extensions.Options;
using Xunit;

namespace Biason.AutomationAgent.IntegrationTests.Connection;

/// <summary>
/// Cobre a conexão WebSocket persistente (seção 11): conectar, reconectar com socket
/// novo após queda, e a garantia de conexão única por instância. Usa
/// <see cref="FakeWebSocketTransport"/> — sem rede real, mas exercitando exatamente o
/// mesmo <c>PortalConnectionManager</c> que roda em produção.
/// </summary>
public sealed class PortalConnectionManagerTests : IAsyncLifetime
{
    private readonly TestHelper _helper = new();

    public async Task InitializeAsync()
    {
        await _helper.InitializeDatabaseAsync();
        await _helper.SeedRegisteredAgentAsync(agentId: "agt_conn", credentialValue: "segredo-teste");
    }

    public Task DisposeAsync()
    {
        _helper.Dispose();
        return Task.CompletedTask;
    }

    private PortalConnectionManager CreateManager(FakeWebSocketTransportFactory factory, PortalOptions? options = null)
    {
        var identity = _helper.CreateIdentityRepository();
        var store = _helper.CreateCredentialStore();
        var connRepo = _helper.CreateConnectionRepository(identity);

        return new PortalConnectionManager(
            factory,
            identity,
            store,
            connRepo,
            _helper.Clock,
            Options.Create(options ?? DefaultOptions()),
            NullLogger<PortalConnectionManager>.Instance);
    }

    private static PortalOptions DefaultOptions() => new()
    {
        Enabled = true,
        ApiBaseUrl = "https://portal.example/api",
        WebSocketUrl = "wss://portal.example/agents/connect",
        ConnectionTimeoutSeconds = 10,
        HeartbeatIntervalSeconds = 5,
        ReconnectInitialSeconds = 1,
        ReconnectMaximumSeconds = 5
    };

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

    private static async Task SafeAwaitAsync(Task task)
    {
        try { await task; }
        catch (OperationCanceledException) { /* esperado no encerramento do teste */ }
    }

    // === websocket-connect ===

    [Fact]
    public async Task Connect_ReachesConnectedState_WithBearerAuthHeader()
    {
        var factory = new FakeWebSocketTransportFactory();
        await using var manager = CreateManager(factory);

        var statesSeen = new List<ConnectionState>();
        manager.StateChanged += (_, to) => { statesSeen.Add(to); return Task.CompletedTask; };

        using var cts = new CancellationTokenSource();
        var runTask = manager.RunAsync(cts.Token);

        await WaitUntilAsync(() => manager.CurrentState == ConnectionState.Connected, TimeSpan.FromSeconds(5));

        var transport = factory.Created.Should().ContainSingle().Which;
        transport.ConnectedHeaders.Should().ContainKey("Authorization");
        transport.ConnectedHeaders!["Authorization"].Should().Be("Bearer segredo-teste");

        statesSeen.Should().ContainInOrder(ConnectionState.Connecting, ConnectionState.Authenticating, ConnectionState.Connected);

        var status = manager.GetStatus();
        status.State.Should().Be(ConnectionState.Connected);
        status.ConnectedAtUtc.Should().NotBeNull();

        // O status também deve ter sido persistido (Incremento 2 usa portal_connections/connection_events).
        var persisted = await _helper.CreateConnectionRepository(_helper.CreateIdentityRepository()).GetLatestStatusAsync();
        persisted.Should().NotBeNull();
        persisted!.State.Should().Be(ConnectionState.Connected);

        cts.Cancel();
        await SafeAwaitAsync(runTask);
    }

    [Fact]
    public async Task Connect_WithoutRegisteredIdentity_StaysDisconnectedAndRetries()
    {
        var freshHelper = new TestHelper();
        try
        {
            await freshHelper.InitializeDatabaseAsync();
            // Nenhum SeedRegisteredAgentAsync aqui — identidade sem agent_id/credencial.

            var identity = freshHelper.CreateIdentityRepository();
            var store = freshHelper.CreateCredentialStore();
            var connRepo = freshHelper.CreateConnectionRepository(identity);
            var factory = new FakeWebSocketTransportFactory();

            await using var manager = new PortalConnectionManager(
                factory, identity, store, connRepo, freshHelper.Clock,
                Options.Create(DefaultOptions()), NullLogger<PortalConnectionManager>.Instance);

            using var cts = new CancellationTokenSource();
            var runTask = manager.RunAsync(cts.Token);

            // Dá tempo para pelo menos uma tentativa falhar por falta de registro.
            await Task.Delay(200);

            manager.CurrentState.Should().Be(ConnectionState.Disconnected);
            factory.Created.Should().BeEmpty("sem identidade registrada, não deve nem tentar abrir socket");

            cts.Cancel();
            await SafeAwaitAsync(runTask);
        }
        finally
        {
            freshHelper.Dispose();
        }
    }

    // === websocket-reconnect ===

    [Fact]
    public async Task ConnectionDrop_TriggersReconnect_WithFreshTransportInstance()
    {
        var factory = new FakeWebSocketTransportFactory();
        await using var manager = CreateManager(factory);

        var statesSeen = new List<ConnectionState>();
        manager.StateChanged += (_, to) => { statesSeen.Add(to); return Task.CompletedTask; };

        using var cts = new CancellationTokenSource();
        var runTask = manager.RunAsync(cts.Token);

        await WaitUntilAsync(() => manager.CurrentState == ConnectionState.Connected, TimeSpan.FromSeconds(5));
        factory.Created.Should().HaveCount(1);
        var firstTransport = factory.Created[0];

        // Portal derruba a conexão (ex.: reinício do lado do servidor).
        firstTransport.EnqueueClose("portal_restart");

        await WaitUntilAsync(
            () => factory.Created.Count == 2 && manager.CurrentState == ConnectionState.Connected,
            TimeSpan.FromSeconds(5));

        factory.Created.Should().HaveCount(2);
        factory.Created[1].Should().NotBeSameAs(firstTransport, "uma conexão morta nunca deve ser reaproveitada");
        statesSeen.Should().Contain(ConnectionState.Reconnecting);

        cts.Cancel();
        await SafeAwaitAsync(runTask);
    }

    [Fact]
    public async Task HandshakeFailure_IsRetried_UntilItSucceeds()
    {
        var attempt = 0;
        var factory = new FakeWebSocketTransportFactory(_ =>
        {
            attempt++;
            var t = new FakeWebSocketTransport();
            if (attempt == 1)
                t.FailConnectWith = new InvalidOperationException("simulated handshake failure");
            return t;
        });

        await using var manager = CreateManager(factory);

        using var cts = new CancellationTokenSource();
        var runTask = manager.RunAsync(cts.Token);

        await WaitUntilAsync(() => manager.CurrentState == ConnectionState.Connected, TimeSpan.FromSeconds(5));

        factory.Created.Should().HaveCount(2, "a primeira tentativa falha no handshake, a segunda conecta");

        cts.Cancel();
        await SafeAwaitAsync(runTask);
    }

    // === websocket-single-connection ===

    [Fact]
    public async Task SecondRunAsyncCall_WhileFirstIsActive_ThrowsInvalidOperationException()
    {
        var factory = new FakeWebSocketTransportFactory();
        await using var manager = CreateManager(factory);

        using var cts = new CancellationTokenSource();
        var firstRun = manager.RunAsync(cts.Token);

        await WaitUntilAsync(() => manager.CurrentState == ConnectionState.Connected, TimeSpan.FromSeconds(5));

        var act = async () => await manager.RunAsync(cts.Token);
        await act.Should().ThrowAsync<InvalidOperationException>();

        // Só um socket deve ter sido aberto — a segunda chamada não tentou conectar de novo.
        factory.Created.Should().HaveCount(1);

        cts.Cancel();
        await SafeAwaitAsync(firstRun);
    }
}
