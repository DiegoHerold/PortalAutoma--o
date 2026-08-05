using System.Text.Json.Serialization;
using Biason.AutomationAgent.Domain.Enums;

namespace Biason.AutomationAgent.Protocol.Messages;

public sealed class AgentSyncStatePayload
{
    [JsonPropertyName("agent_id")]
    public string? AgentId { get; init; }

    [JsonPropertyName("instance_id")]
    public string? InstanceId { get; init; }

    [JsonPropertyName("agent_state")]
    public string AgentState { get; init; } = "unknown";

    [JsonPropertyName("reason")]
    public string Reason { get; init; } = "manual";

    [JsonPropertyName("sent_at")]
    public DateTime SentAt { get; init; }

    [JsonPropertyName("running_executions")]
    public IReadOnlyList<AgentSyncExecutionItem> RunningExecutions { get; init; } = Array.Empty<AgentSyncExecutionItem>();

    [JsonPropertyName("reservations")]
    public IReadOnlyList<AgentSyncReservationItem> Reservations { get; init; } = Array.Empty<AgentSyncReservationItem>();

    [JsonPropertyName("leases")]
    public IReadOnlyList<AgentSyncLeaseItem> Leases { get; init; } = Array.Empty<AgentSyncLeaseItem>();

    [JsonPropertyName("interactive_sessions")]
    public IReadOnlyList<object> InteractiveSessions { get; init; } = Array.Empty<object>();

    [JsonPropertyName("outbox_summary")]
    public object? OutboxSummary { get; init; }

    [JsonPropertyName("inbox_summary")]
    public object? InboxSummary { get; init; }

    [JsonPropertyName("pending_artifacts")]
    public IReadOnlyList<AgentSyncArtifactItem> PendingArtifacts { get; init; } = Array.Empty<AgentSyncArtifactItem>();

    [JsonPropertyName("reconciliation")]
    public IReadOnlyList<AgentSyncReconciliationItem> Reconciliation { get; init; } = Array.Empty<AgentSyncReconciliationItem>();
}

public sealed class AgentSyncExecutionItem
{
    [JsonPropertyName("execution_id")]
    public string ExecutionId { get; init; } = default!;

    [JsonPropertyName("execution_attempt_id")]
    public string? ExecutionAttemptId { get; init; }

    [JsonPropertyName("state")]
    public string State { get; init; } = default!;

    [JsonPropertyName("reservation_id")]
    public string? ReservationId { get; init; }

    [JsonPropertyName("workspace_path")]
    public string? WorkspacePath { get; init; }
}

public sealed class AgentSyncReservationItem
{
    [JsonPropertyName("reservation_id")]
    public string ReservationId { get; init; } = default!;

    [JsonPropertyName("execution_id")]
    public string ExecutionId { get; init; } = default!;

    [JsonPropertyName("pool")]
    public string Pool { get; init; } = default!;

    [JsonPropertyName("slots")]
    public int Slots { get; init; }

    [JsonPropertyName("status")]
    public string Status { get; init; } = default!;

    [JsonPropertyName("expires_at")]
    public DateTime ExpiresAt { get; init; }
}

public sealed class AgentSyncLeaseItem
{
    [JsonPropertyName("lease_id")]
    public string LeaseId { get; init; } = default!;

    [JsonPropertyName("execution_id")]
    public string ExecutionId { get; init; } = default!;

    [JsonPropertyName("execution_attempt_id")]
    public string ExecutionAttemptId { get; init; } = default!;

    [JsonPropertyName("state")]
    public string State { get; init; } = default!;

    [JsonPropertyName("expires_at")]
    public DateTime ExpiresAt { get; init; }
}

public sealed class AgentSyncArtifactItem
{
    [JsonPropertyName("artifact_id")]
    public string ArtifactId { get; init; } = default!;

    [JsonPropertyName("execution_id")]
    public string ExecutionId { get; init; } = default!;

    [JsonPropertyName("execution_attempt_id")]
    public string ExecutionAttemptId { get; init; } = default!;

    [JsonPropertyName("name")]
    public string Name { get; init; } = default!;

    [JsonPropertyName("status")]
    public string Status { get; init; } = default!;

    [JsonPropertyName("size_bytes")]
    public long SizeBytes { get; init; }
}

public sealed class AgentSyncReconciliationItem
{
    [JsonPropertyName("execution_id")]
    public string ExecutionId { get; init; } = default!;

    [JsonPropertyName("result")]
    public ExecutionReconciliationResult Result { get; init; }

    [JsonPropertyName("details")]
    public string? Details { get; init; }
}
