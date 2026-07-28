using System.Text.Json.Serialization;

namespace Biason.AutomationAgent.Protocol.Capacity;

/// <summary>
/// Wire format aligned with contracts/capacity/capacity-snapshot.schema.json
/// </summary>
public sealed class CapacitySnapshotDto
{
    [JsonPropertyName("agent_id")]
    public string AgentId { get; init; } = default!;

    [JsonPropertyName("agent_instance_id")]
    public string AgentInstanceId { get; init; } = default!;

    [JsonPropertyName("observed_at")]
    public DateTime ObservedAt { get; init; }

    [JsonPropertyName("revision")]
    public int Revision { get; init; }

    [JsonPropertyName("ttl_seconds")]
    public int TtlSeconds { get; init; }

    [JsonPropertyName("pools")]
    public PoolsDto Pools { get; init; } = default!;
}

public sealed class PoolsDto
{
    [JsonPropertyName("interactive")]
    public PoolCapacityDto Interactive { get; init; } = default!;

    [JsonPropertyName("background")]
    public PoolCapacityDto Background { get; init; } = default!;

    [JsonPropertyName("browser")]
    public PoolCapacityDto Browser { get; init; } = default!;
}

/// <summary>
/// Wire format aligned with contracts/capacity/pool-capacity.schema.json
/// </summary>
public sealed class PoolCapacityDto
{
    [JsonPropertyName("recommended_total")]
    public int RecommendedTotal { get; init; }

    [JsonPropertyName("administrator_total")]
    public int AdministratorTotal { get; init; }

    [JsonPropertyName("effective_total")]
    public int EffectiveTotal { get; init; }

    [JsonPropertyName("used")]
    public int Used { get; init; }

    [JsonPropertyName("reserved")]
    public int Reserved { get; init; }

    [JsonPropertyName("available")]
    public int Available { get; init; }
}
