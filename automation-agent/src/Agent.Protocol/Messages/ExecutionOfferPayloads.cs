using System.Text.Json;
using System.Text.Json.Serialization;

namespace Biason.AutomationAgent.Protocol.Messages;

/// <summary>Payload de execution.offer (Portal -> Agent).</summary>
public sealed class ExecutionOfferPayload
{
    [JsonPropertyName("execution_offer_id")]
    public string ExecutionOfferId { get; init; } = default!;

    [JsonPropertyName("execution_id")]
    public string? ExecutionId { get; init; }

    [JsonPropertyName("execution_attempt_id")]
    public string ExecutionAttemptId { get; init; } = default!;

    [JsonPropertyName("task_execution_id")]
    public string TaskExecutionId { get; init; } = default!;

    [JsonPropertyName("agent_id")]
    public string? AgentId { get; init; }

    [JsonPropertyName("agent_instance_id")]
    public string? AgentInstanceId { get; init; }

    [JsonPropertyName("automation_id")]
    public string? AutomationId { get; init; }

    [JsonPropertyName("automation_version")]
    public string? AutomationVersion { get; init; }

    [JsonPropertyName("automation_version_id")]
    public string AutomationVersionId { get; init; } = default!;

    [JsonPropertyName("execution_mode")]
    public string? ExecutionMode { get; init; }

    [JsonPropertyName("runtime")]
    public ExecutionOfferRuntime Runtime { get; init; } = default!;

    [JsonPropertyName("package")]
    public ExecutionOfferPackage Package { get; init; } = default!;

    [JsonPropertyName("input")]
    public JsonElement Input { get; init; }

    [JsonPropertyName("resources")]
    public IReadOnlyDictionary<string, int>? Resources { get; init; }

    [JsonPropertyName("capabilities")]
    public IReadOnlyList<ExecutionOfferCapabilityRequirement>? Capabilities { get; init; }

    [JsonPropertyName("required_capabilities")]
    public IReadOnlyList<ExecutionOfferCapabilityRequirement>? RequiredCapabilities { get; init; }

    [JsonPropertyName("required_pools")]
    public IReadOnlyList<string> RequiredPools { get; init; } = Array.Empty<string>();

    [JsonPropertyName("resource_locks")]
    public IReadOnlyList<string>? ResourceLocks { get; init; }

    [JsonPropertyName("expires_at")]
    public DateTime ExpiresAt { get; init; }

    [JsonPropertyName("reservation_ttl_seconds")]
    public int? ReservationTtlSeconds { get; init; }
}

public sealed class ExecutionOfferRuntime
{
    [JsonPropertyName("id")]
    public string Id { get; init; } = default!;

    [JsonPropertyName("version")]
    public string? Version { get; init; }
}

public sealed class ExecutionOfferPackage
{
    [JsonPropertyName("id")]
    public string Id { get; init; } = default!;

    [JsonPropertyName("download_url")]
    public string? DownloadUrl { get; init; }

    [JsonPropertyName("sha256")]
    public string Sha256 { get; init; } = default!;

    [JsonPropertyName("size_bytes")]
    public long? SizeBytes { get; init; }
}

public sealed class ExecutionOfferCapabilityRequirement
{
    [JsonPropertyName("key")]
    public string Key { get; init; } = default!;
}

/// <summary>Payload de execution.accepted (Agent -> Portal).</summary>
public sealed class ExecutionAcceptPayload
{
    [JsonPropertyName("execution_offer_id")]
    public string ExecutionOfferId { get; init; } = default!;

    [JsonPropertyName("execution_attempt_id")]
    public string ExecutionAttemptId { get; init; } = default!;

    [JsonPropertyName("agent_id")]
    public string AgentId { get; init; } = default!;

    [JsonPropertyName("agent_instance_id")]
    public string AgentInstanceId { get; init; } = default!;

    [JsonPropertyName("accepted_at")]
    public DateTime AcceptedAt { get; init; }

    [JsonPropertyName("reserved_pools")]
    public IReadOnlyDictionary<string, int>? ReservedPools { get; init; }

    [JsonPropertyName("resource_reservations")]
    public IReadOnlyList<string>? ResourceReservations { get; init; }
}

/// <summary>Payload de execution.rejected (Agent -> Portal).</summary>
public sealed class ExecutionRejectPayload
{
    [JsonPropertyName("execution_offer_id")]
    public string ExecutionOfferId { get; init; } = default!;

    [JsonPropertyName("execution_attempt_id")]
    public string ExecutionAttemptId { get; init; } = default!;

    [JsonPropertyName("task_execution_id")]
    public string? TaskExecutionId { get; init; }

    [JsonPropertyName("agent_id")]
    public string AgentId { get; init; } = default!;

    [JsonPropertyName("agent_instance_id")]
    public string AgentInstanceId { get; init; } = default!;

    [JsonPropertyName("rejection_code")]
    public string RejectionCode { get; init; } = default!;

    [JsonPropertyName("rejection_details")]
    public IReadOnlyDictionary<string, object?>? RejectionDetails { get; init; }

    [JsonPropertyName("rejected_at")]
    public DateTime RejectedAt { get; init; }
}
