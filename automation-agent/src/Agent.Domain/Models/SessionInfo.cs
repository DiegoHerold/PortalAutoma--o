using Biason.AutomationAgent.Domain.Enums;

namespace Biason.AutomationAgent.Domain.Models;

public sealed class SessionInfo
{
    public SessionStatus Status { get; init; }
    public bool? IsLocked { get; init; }
    public string? User { get; init; }
    public int? SessionId { get; init; }
    public SessionType Type { get; init; }
    public int? ScreenWidth { get; init; }
    public int? ScreenHeight { get; init; }
    public int? MonitorCount { get; init; }
}
