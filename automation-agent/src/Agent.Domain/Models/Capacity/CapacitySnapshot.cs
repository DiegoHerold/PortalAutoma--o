using Biason.AutomationAgent.Domain.Enums;

namespace Biason.AutomationAgent.Domain.Models.Capacity;

public sealed class CapacitySnapshot
{
    public string AgentId { get; init; } = default!;
    public string AgentInstanceId { get; init; } = default!;
    public DateTime ObservedAt { get; init; }
    public int Revision { get; init; }
    public int TtlSeconds { get; init; } = 60;
    public Dictionary<PoolType, PoolCapacity> Pools { get; init; } = new();
}
