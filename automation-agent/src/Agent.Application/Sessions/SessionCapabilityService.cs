using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Sessions;

namespace Biason.AutomationAgent.Application.Sessions;

public sealed class SessionCapabilityService : ISessionCapabilityService
{
    private readonly IInteractiveSessionRepository _sessions;
    private readonly IClock _clock;
    private readonly ICapabilityRepository? _capabilities;

    public SessionCapabilityService(IInteractiveSessionRepository sessions, IClock clock, ICapabilityRepository? capabilities = null)
    {
        _sessions = sessions;
        _clock = clock;
        _capabilities = capabilities;
    }

    public async Task<IReadOnlyList<DynamicSessionCapability>> GetCapabilitiesAsync(CancellationToken ct = default)
    {
        var now = _clock.UtcNow;
        var sessions = await _sessions.GetAllAsync(ct);
        var globalAvailable = _capabilities is null
            ? new HashSet<string>(StringComparer.OrdinalIgnoreCase)
            : (await _capabilities.GetAllAsync(ct))
                .Where(c => c.Status == CapabilityStatus.Available)
                .Select(c => c.Key)
                .ToHashSet(StringComparer.OrdinalIgnoreCase);
        var caps = new List<DynamicSessionCapability>();

        foreach (var session in sessions)
        {
            var connected = session.SessionRunnerInstanceId is not null;
            var active = session.State == WindowsSessionState.Active;
            var unlocked = session.IsLocked == false && session.State != WindowsSessionState.Locked;
            var desktopReady = active && unlocked;
            var automationReady = desktopReady && connected;
            caps.Add(Cap("interactive_session", active && unlocked && connected, session.SessionId, now));
            caps.Add(Cap("session_runner_connected", connected, session.SessionId, now));
            caps.Add(Cap("desktop_available", desktopReady, session.SessionId, now));
            caps.Add(Cap("desktop_unlocked", unlocked, session.SessionId, now));
            caps.Add(Cap("desktop_automation", automationReady, session.SessionId, now));
            caps.Add(Cap(session.SessionType == SessionType.Rdp ? "rdp_session" : "local_session", true, session.SessionId, now));
            caps.Add(Cap("office.excel", automationReady && globalAvailable.Contains("office.excel"), session.SessionId, now));
            caps.Add(Cap("dominio.installed", automationReady && globalAvailable.Contains("dominio.installed"), session.SessionId, now));
        }

        return caps;
    }

    private static DynamicSessionCapability Cap(string key, bool available, int sessionId, DateTime now) => new()
    {
        Key = key,
        Status = available ? CapabilityStatus.Available : CapabilityStatus.Unavailable,
        SessionId = sessionId,
        ObservedAtUtc = now
    };
}
