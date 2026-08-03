using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Sessions;
using Biason.AutomationAgent.IntegrationTests.Helpers;
using FluentAssertions;
using Xunit;

namespace Biason.AutomationAgent.IntegrationTests.Sessions;

public sealed class SessionPersistenceTests : IAsyncLifetime
{
    private readonly TestHelper _helper = new();

    public async Task InitializeAsync() => await _helper.InitializeDatabaseAsync();

    public Task DisposeAsync()
    {
        _helper.Dispose();
        return Task.CompletedTask;
    }

    [Fact]
    public async Task InteractiveSession_Upsert_RoundTrips()
    {
        var repo = _helper.CreateInteractiveSessionRepository();

        await repo.UpsertAsync(new InteractiveSessionRecord
        {
            SessionId = 2,
            UserName = "usuario",
            DomainName = "CONTABIL",
            StationName = "Console",
            SessionType = SessionType.Local,
            State = WindowsSessionState.Active,
            IsLocked = false,
            ScreenWidth = 1920,
            ScreenHeight = 1080,
            MonitorCount = 2,
            DpiScale = 1.25,
            ObservedAtUtc = DateTime.UtcNow
        });

        var loaded = await repo.GetAsync(2);

        loaded.Should().NotBeNull();
        loaded!.State.Should().Be(WindowsSessionState.Active);
        loaded.IsLocked.Should().BeFalse();
        loaded.MonitorCount.Should().Be(2);
    }

    [Fact]
    public async Task SessionRunner_HeartbeatAndDisconnect_ArePersisted()
    {
        var runners = _helper.CreateSessionRunnerRepository();
        var now = DateTime.UtcNow;

        await runners.UpsertAsync(new SessionRunnerRecord
        {
            InstanceId = "sr_test",
            SessionId = 2,
            UserName = "CONTABIL\\usuario",
            SessionType = SessionType.Local,
            ProcessId = 4321,
            Version = "0.4.0",
            State = SessionRunnerConnectionState.Connected,
            RegisteredAtUtc = now,
            LastHeartbeatAtUtc = now,
            Desktop = new DesktopState { Available = true, Locked = false }
        });

        await runners.UpdateHeartbeatAsync("sr_test", now.AddSeconds(5), new DesktopState { Available = true, Locked = true });
        await runners.MarkDisconnectedAsync("sr_test", now.AddSeconds(10), "test");

        var loaded = await runners.GetAsync("sr_test");
        loaded.Should().NotBeNull();
        loaded!.State.Should().Be(SessionRunnerConnectionState.Disconnected);
        loaded.DisconnectedAtUtc.Should().NotBeNull();
        loaded.SessionTokenFingerprint.Should().BeNull();
    }

    [Fact]
    public async Task SessionEvents_AndConnectionHistory_ArePersisted()
    {
        var events = _helper.CreateSessionEventRepository();
        var connections = _helper.CreateSessionRunnerConnectionRepository();
        var now = DateTime.UtcNow;

        await events.AddAsync(new SessionEventRecord
        {
            SessionId = 2,
            SessionRunnerInstanceId = "sr_test",
            EventType = "session.locked",
            DetailJson = "{}",
            OccurredAtUtc = now
        });

        var connectionId = await connections.AddAsync(new SessionRunnerConnectionRecord
        {
            SessionRunnerInstanceId = "sr_test",
            SessionId = 2,
            ConnectedAtUtc = now,
            RemoteProcessId = 4321,
            ProtocolVersion = "1.0",
            Status = "connected"
        });
        await connections.MarkAuthenticatedAsync(connectionId, now.AddSeconds(1));
        await connections.MarkDisconnectedAsync(connectionId, now.AddSeconds(2), "test");

        (await events.GetRecentAsync(10)).Should().ContainSingle(e => e.EventType == "session.locked");
        var recentConnections = await connections.GetRecentAsync(10);
        recentConnections.Should().ContainSingle();
        recentConnections[0].Status.Should().Be("disconnected");
        recentConnections[0].AuthenticatedAtUtc.Should().NotBeNull();
    }
}
