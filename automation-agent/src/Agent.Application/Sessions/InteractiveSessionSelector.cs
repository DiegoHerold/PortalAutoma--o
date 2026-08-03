using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Sessions;

namespace Biason.AutomationAgent.Application.Sessions;

public sealed class InteractiveSessionSelector : IInteractiveSessionSelector
{
    private readonly IInteractiveSessionRepository _sessions;
    private readonly IWindowsSessionDiscovery _discovery;

    public InteractiveSessionSelector(IInteractiveSessionRepository sessions, IWindowsSessionDiscovery discovery)
    {
        _sessions = sessions;
        _discovery = discovery;
    }

    public async Task<InteractiveSessionSelectionResult> SelectAsync(InteractiveSessionSelectionRequest request, CancellationToken ct = default)
    {
        return request.Policy switch
        {
            InteractiveSessionSelectionPolicy.ActiveUnlocked => await SelectActiveUnlockedAsync(ct),
            InteractiveSessionSelectionPolicy.CurrentConsoleSession => await SelectConsoleAsync(ct),
            InteractiveSessionSelectionPolicy.SpecificSession when request.SessionId.HasValue => await ValidateAsync(request.SessionId.Value, ct),
            InteractiveSessionSelectionPolicy.SpecificSession => InteractiveSessionSelectionResult.Rejected("MISSING_SESSION_ID", "specific_session requires session_id."),
            _ => InteractiveSessionSelectionResult.Rejected("UNKNOWN_POLICY", "Unknown interactive session selection policy.")
        };
    }

    private async Task<InteractiveSessionSelectionResult> SelectActiveUnlockedAsync(CancellationToken ct)
    {
        var sessions = await _sessions.GetAllAsync(ct);
        var selected = sessions
            .Where(IsUsable)
            .OrderByDescending(s => s.SessionType == SessionType.Local)
            .ThenBy(s => s.SessionId)
            .FirstOrDefault();

        return selected is null
            ? InteractiveSessionSelectionResult.Rejected("NO_ACTIVE_UNLOCKED_SESSION", "No active unlocked session with connected runner was found.")
            : InteractiveSessionSelectionResult.Selected(selected);
    }

    private async Task<InteractiveSessionSelectionResult> SelectConsoleAsync(CancellationToken ct)
    {
        var consoleId = _discovery.GetActiveConsoleSessionId();
        if (consoleId is null)
            return InteractiveSessionSelectionResult.Rejected("NO_CONSOLE_SESSION", "No active console session was reported by Windows.");

        return await ValidateAsync(consoleId.Value, ct);
    }

    private async Task<InteractiveSessionSelectionResult> ValidateAsync(int sessionId, CancellationToken ct)
    {
        var session = await _sessions.GetAsync(sessionId, ct);
        if (session is null)
            return InteractiveSessionSelectionResult.Rejected("SESSION_NOT_FOUND", $"Session {sessionId} was not found.");

        if (session.State is WindowsSessionState.Disconnected or WindowsSessionState.Terminated)
            return InteractiveSessionSelectionResult.Rejected("SESSION_DISCONNECTED", $"Session {sessionId} is not connected.");

        if (session.IsLocked == true || session.State == WindowsSessionState.Locked)
            return InteractiveSessionSelectionResult.Rejected("SESSION_LOCKED", $"Session {sessionId} is locked.");

        if (session.SessionRunnerInstanceId is null)
            return InteractiveSessionSelectionResult.Rejected("SESSION_RUNNER_MISSING", $"Session {sessionId} has no connected Session Runner.");

        return IsUsable(session)
            ? InteractiveSessionSelectionResult.Selected(session)
            : InteractiveSessionSelectionResult.Rejected("DESKTOP_UNAVAILABLE", $"Session {sessionId} desktop is not available.");
    }

    private static bool IsUsable(InteractiveSessionRecord s) =>
        s.State == WindowsSessionState.Active &&
        s.IsLocked == false &&
        s.SessionRunnerInstanceId is not null;
}
