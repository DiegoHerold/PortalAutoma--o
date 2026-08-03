using Biason.AutomationAgent.Application.Sessions;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Sessions;
using FluentAssertions;
using Xunit;

namespace Biason.AutomationAgent.UnitTests.Sessions;

public sealed class InteractiveSessionSelectorTests
{
    [Fact]
    public async Task ActiveUnlocked_SelectsUsableSession()
    {
        var repo = new FakeInteractiveSessionRepository(new[]
        {
            Session(1, WindowsSessionState.Locked, true, "sr_locked"),
            Session(2, WindowsSessionState.Active, false, "sr_ok")
        });
        var selector = new InteractiveSessionSelector(repo, new FakeDiscovery(consoleSessionId: 2));

        var result = await selector.SelectAsync(new InteractiveSessionSelectionRequest
        {
            Policy = InteractiveSessionSelectionPolicy.ActiveUnlocked
        });

        result.Success.Should().BeTrue();
        result.Session!.SessionId.Should().Be(2);
    }

    [Fact]
    public async Task LockedSession_IsRejected()
    {
        var repo = new FakeInteractiveSessionRepository(new[] { Session(2, WindowsSessionState.Locked, true, "sr_1") });
        var selector = new InteractiveSessionSelector(repo, new FakeDiscovery(consoleSessionId: 2));

        var result = await selector.SelectAsync(new InteractiveSessionSelectionRequest
        {
            Policy = InteractiveSessionSelectionPolicy.SpecificSession,
            SessionId = 2
        });

        result.Success.Should().BeFalse();
        result.RejectionCode.Should().Be("SESSION_LOCKED");
    }

    [Fact]
    public async Task SessionWithoutRunner_IsRejected()
    {
        var repo = new FakeInteractiveSessionRepository(new[] { Session(2, WindowsSessionState.Active, false, null) });
        var selector = new InteractiveSessionSelector(repo, new FakeDiscovery(consoleSessionId: 2));

        var result = await selector.SelectAsync(new InteractiveSessionSelectionRequest
        {
            Policy = InteractiveSessionSelectionPolicy.SpecificSession,
            SessionId = 2
        });

        result.Success.Should().BeFalse();
        result.RejectionCode.Should().Be("SESSION_RUNNER_MISSING");
    }

    private static InteractiveSessionRecord Session(int id, WindowsSessionState state, bool? locked, string? runner) => new()
    {
        SessionId = id,
        State = state,
        IsLocked = locked,
        SessionType = SessionType.Local,
        SessionRunnerInstanceId = runner,
        ObservedAtUtc = DateTime.UtcNow
    };

    private sealed class FakeInteractiveSessionRepository : IInteractiveSessionRepository
    {
        private readonly List<InteractiveSessionRecord> _sessions;
        public FakeInteractiveSessionRepository(IEnumerable<InteractiveSessionRecord> sessions) => _sessions = sessions.ToList();
        public Task UpsertAsync(InteractiveSessionRecord session, CancellationToken ct = default) => Task.CompletedTask;
        public Task<InteractiveSessionRecord?> GetAsync(int sessionId, CancellationToken ct = default) => Task.FromResult(_sessions.FirstOrDefault(s => s.SessionId == sessionId));
        public Task<IReadOnlyList<InteractiveSessionRecord>> GetAllAsync(CancellationToken ct = default) => Task.FromResult<IReadOnlyList<InteractiveSessionRecord>>(_sessions);
        public Task AttachRunnerAsync(int sessionId, string? instanceId, DateTime observedAtUtc, CancellationToken ct = default) => Task.CompletedTask;
    }

    private sealed class FakeDiscovery : IWindowsSessionDiscovery
    {
        private readonly int? _consoleSessionId;
        public FakeDiscovery(int? consoleSessionId) => _consoleSessionId = consoleSessionId;
        public Task<IReadOnlyList<WindowsSession>> DiscoverAsync(CancellationToken ct = default) => Task.FromResult<IReadOnlyList<WindowsSession>>(Array.Empty<WindowsSession>());
        public int? GetActiveConsoleSessionId() => _consoleSessionId;
    }
}
