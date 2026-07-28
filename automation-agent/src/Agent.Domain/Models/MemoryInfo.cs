namespace Biason.AutomationAgent.Domain.Models;

public sealed class MemoryInfo
{
    public long TotalMb { get; init; }
    public long AvailableMb { get; init; }
    public long UsedMb { get; init; }
    public double UsagePercent { get; init; }
    public long AgentMemoryMb { get; init; }
}
