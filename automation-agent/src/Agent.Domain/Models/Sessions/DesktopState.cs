namespace Biason.AutomationAgent.Domain.Models.Sessions;

public sealed class DesktopState
{
    public bool? Available { get; init; }
    public bool? Locked { get; init; }
    public DesktopResolution? Resolution { get; init; }
    public int? MonitorCount { get; init; }
    public double? DpiScale { get; init; }

    public static DesktopState Unknown { get; } = new();
}
