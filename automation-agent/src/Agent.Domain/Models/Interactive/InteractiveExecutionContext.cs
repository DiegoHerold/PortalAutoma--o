using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Sessions;

namespace Biason.AutomationAgent.Domain.Models.Interactive;

public sealed class InteractiveExecutionContext
{
    public int SessionId { get; init; }
    public SessionType SessionType { get; init; } = SessionType.Unknown;
    public DesktopResolution? DesktopResolution { get; init; }
    public double? DpiScale { get; init; }
    public int? MonitorCount { get; init; }
    public string SessionRunnerInstanceId { get; init; } = default!;
    public bool DesktopLocked { get; init; }
}
