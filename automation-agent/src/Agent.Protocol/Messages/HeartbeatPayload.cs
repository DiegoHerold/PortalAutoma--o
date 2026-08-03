using System.Text.Json.Serialization;

namespace Biason.AutomationAgent.Protocol.Messages;

/// <summary>
/// Payload de <c>agent.heartbeat</c> (seção 16). Deliberadamente leve — o perfil
/// completo da máquina não vai aqui, só o essencial para o Portal saber que o
/// Agent está vivo e qual sua capacidade agora.
/// </summary>
public sealed class HeartbeatPayload
{
    [JsonPropertyName("agent_id")]
    public string? AgentId { get; init; }

    [JsonPropertyName("instance_id")]
    public string InstanceId { get; init; } = default!;

    [JsonPropertyName("version")]
    public string Version { get; init; } = default!;

    [JsonPropertyName("state")]
    public string State { get; init; } = default!;

    [JsonPropertyName("connection_state")]
    public string ConnectionState { get; init; } = default!;

    [JsonPropertyName("profile")]
    public string? Profile { get; init; }

    [JsonPropertyName("last_profile_at")]
    public DateTime? LastProfileAtUtc { get; init; }

    [JsonPropertyName("capacity")]
    public HeartbeatCapacity Capacity { get; init; } = default!;

    [JsonPropertyName("resources")]
    public HeartbeatResources? Resources { get; init; }

    [JsonPropertyName("interactive_session")]
    public HeartbeatInteractiveSession? InteractiveSession { get; init; }

    [JsonPropertyName("running_executions")]
    public int RunningExecutions { get; init; }

    [JsonPropertyName("outbox_pending")]
    public int OutboxPending { get; init; }

    [JsonPropertyName("pending_artifacts")]
    public int PendingArtifacts { get; init; }
}

public sealed class HeartbeatCapacity
{
    [JsonPropertyName("global")]
    public HeartbeatPoolCapacity Global { get; init; } = default!;

    [JsonPropertyName("background")]
    public HeartbeatPoolCapacity Background { get; init; } = default!;

    [JsonPropertyName("browser")]
    public HeartbeatPoolCapacity Browser { get; init; } = default!;

    [JsonPropertyName("interactive")]
    public HeartbeatPoolCapacity Interactive { get; init; } = default!;
}

public sealed class HeartbeatPoolCapacity
{
    [JsonPropertyName("total")]
    public int Total { get; init; }

    [JsonPropertyName("used")]
    public int Used { get; init; }

    [JsonPropertyName("reserved")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public int? Reserved { get; init; }
}

public sealed class HeartbeatResources
{
    [JsonPropertyName("cpu_percentage")]
    public double CpuPercentage { get; init; }

    [JsonPropertyName("memory_percentage")]
    public double MemoryPercentage { get; init; }

    [JsonPropertyName("disk_free_mb")]
    public long DiskFreeMb { get; init; }
}

/// <summary>
/// Antes da Fase 3 ter Session Runner (incremento 7+), <c>Available</c> é sempre
/// false — não há como saber se existe sessão interativa sem ele.
/// </summary>
public sealed class HeartbeatInteractiveSession
{
    [JsonPropertyName("available")]
    public bool Available { get; init; }

    [JsonPropertyName("locked")]
    public bool? Locked { get; init; }

    [JsonPropertyName("session_id")]
    public int? SessionId { get; init; }
}
