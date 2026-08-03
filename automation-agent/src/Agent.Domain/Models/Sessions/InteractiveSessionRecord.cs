using Biason.AutomationAgent.Domain.Enums;

namespace Biason.AutomationAgent.Domain.Models.Sessions;

public sealed class InteractiveSessionRecord
{
    public int SessionId { get; init; }
    public string? UserName { get; init; }
    public string? DomainName { get; init; }
    public string? StationName { get; init; }
    public SessionType SessionType { get; init; } = SessionType.Unknown;
    public WindowsSessionState State { get; init; } = WindowsSessionState.Unknown;
    public bool? IsLocked { get; init; }
    public int? ScreenWidth { get; init; }
    public int? ScreenHeight { get; init; }
    public int? MonitorCount { get; init; }
    public double? DpiScale { get; init; }
    public string? SessionRunnerInstanceId { get; init; }
    public DateTime ObservedAtUtc { get; init; }

    public bool IsDesktopAvailable =>
        State == WindowsSessionState.Active &&
        IsLocked == false &&
        SessionRunnerInstanceId is not null;
}
