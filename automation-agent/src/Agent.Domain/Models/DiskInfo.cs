namespace Biason.AutomationAgent.Domain.Models;

public sealed class DiskInfo
{
    public string Volume { get; init; } = default!;
    public string? FileSystem { get; init; }
    public long TotalMb { get; init; }
    public long FreeMb { get; init; }
    public double UsagePercent { get; init; }
    public string DataDirectory { get; init; } = default!;
    public long MinimumFreeMb { get; init; }
}
