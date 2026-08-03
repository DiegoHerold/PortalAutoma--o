using Biason.AutomationAgent.Domain.Enums;

namespace Biason.AutomationAgent.Domain.Models.Sessions;

public sealed class WindowsSession
{
    public int SessionId { get; init; }
    public string? User { get; init; }
    public string? Domain { get; init; }
    public string? StationName { get; init; }
    public WindowsSessionState State { get; init; } = WindowsSessionState.Unknown;
    public SessionType Type { get; init; } = SessionType.Unknown;
    public bool IsConsole { get; init; }
    public bool IsRdp { get; init; }
    public bool IsActive => State == WindowsSessionState.Active;
    public bool IsConnected => State is WindowsSessionState.Active or WindowsSessionState.Connected;
    public DesktopState Desktop { get; init; } = DesktopState.Unknown;
    public DateTime ObservedAtUtc { get; init; }
}
