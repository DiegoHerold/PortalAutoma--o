using Biason.AutomationAgent.Application.Sessions;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Sessions;
using FluentAssertions;
using Xunit;

namespace Biason.AutomationAgent.UnitTests.Sessions;

public sealed class SessionCapabilityServiceTests
{
    [Fact]
    public async Task ConnectedUnlockedSession_ReportsInteractiveCapabilitiesAvailable()
    {
        var service = new SessionCapabilityService(
            new FakeInteractiveSessionRepository(new[]
            {
                new InteractiveSessionRecord
                {
                    SessionId = 2,
                    State = WindowsSessionState.Active,
                    IsLocked = false,
                    SessionType = SessionType.Local,
                    SessionRunnerInstanceId = "sr_1",
                    ObservedAtUtc = DateTime.UtcNow
                }
            }),
            new FakeClock());

        var caps = await service.GetCapabilitiesAsync();

        caps.Should().Contain(c => c.Key == "interactive_session" && c.Status == CapabilityStatus.Available);
        caps.Should().Contain(c => c.Key == "session_runner_connected" && c.Status == CapabilityStatus.Available);
        caps.Should().Contain(c => c.Key == "desktop_unlocked" && c.Status == CapabilityStatus.Available);
        caps.Should().Contain(c => c.Key == "desktop_automation" && c.Status == CapabilityStatus.Available);
    }

    [Fact]
    public async Task LockedSession_ReportsDesktopUnlockedUnavailable()
    {
        var service = new SessionCapabilityService(
            new FakeInteractiveSessionRepository(new[]
            {
                new InteractiveSessionRecord
                {
                    SessionId = 2,
                    State = WindowsSessionState.Locked,
                    IsLocked = true,
                    SessionType = SessionType.Local,
                    SessionRunnerInstanceId = "sr_1",
                    ObservedAtUtc = DateTime.UtcNow
                }
            }),
            new FakeClock());

        var caps = await service.GetCapabilitiesAsync();

        caps.Should().Contain(c => c.Key == "desktop_unlocked" && c.Status == CapabilityStatus.Unavailable);
        caps.Should().Contain(c => c.Key == "interactive_session" && c.Status == CapabilityStatus.Unavailable);
    }

    private sealed class FakeInteractiveSessionRepository : IInteractiveSessionRepository
    {
        private readonly IReadOnlyList<InteractiveSessionRecord> _sessions;
        public FakeInteractiveSessionRepository(IReadOnlyList<InteractiveSessionRecord> sessions) => _sessions = sessions;
        public Task UpsertAsync(InteractiveSessionRecord session, CancellationToken ct = default) => Task.CompletedTask;
        public Task<InteractiveSessionRecord?> GetAsync(int sessionId, CancellationToken ct = default) => Task.FromResult(_sessions.FirstOrDefault(s => s.SessionId == sessionId));
        public Task<IReadOnlyList<InteractiveSessionRecord>> GetAllAsync(CancellationToken ct = default) => Task.FromResult(_sessions);
        public Task AttachRunnerAsync(int sessionId, string? instanceId, DateTime observedAtUtc, CancellationToken ct = default) => Task.CompletedTask;
    }

    private sealed class FakeClock : IClock
    {
        public DateTime UtcNow => DateTime.UtcNow;
    }
}
