using System.Text.Json.Serialization;

namespace Biason.AutomationAgent.Protocol.Messages;

/// <summary>
/// Payload de <c>execution.commit</c> (Portal -&gt; Agent), conforme
/// contracts/messages/portal-to-agent/execution-commit.schema.json.
/// Note: o contrato real não carrega reservation_id — a correlação é feita
/// por execution_offer_id/execution_attempt_id, e o lease já vem concedido
/// junto com o commit (lease_id/lease_expires_at), não solicitado depois.
/// </summary>
public sealed class ExecutionCommitPayload
{
    [JsonPropertyName("execution_offer_id")]
    public string ExecutionOfferId { get; init; } = default!;

    [JsonPropertyName("execution_id")]
    public string? ExecutionId { get; init; }

    [JsonPropertyName("execution_attempt_id")]
    public string ExecutionAttemptId { get; init; } = default!;

    [JsonPropertyName("task_execution_id")]
    public string? TaskExecutionId { get; init; }

    [JsonPropertyName("agent_id")]
    public string? AgentId { get; init; }

    [JsonPropertyName("agent_instance_id")]
    public string? AgentInstanceId { get; init; }

    [JsonPropertyName("lease_id")]
    public string LeaseId { get; init; } = default!;

    [JsonPropertyName("lease_expires_at")]
    public DateTime LeaseExpiresAt { get; init; }

    [JsonPropertyName("command_sequence")]
    public long? CommandSequence { get; init; }
}

/// <summary>Payload de resposta <c>execution.commit_rejected</c> (Agent -&gt; Portal), Bloco 5.5 seção 16.</summary>
public sealed class ExecutionCommitRejectedPayload
{
    [JsonPropertyName("execution_offer_id")]
    public string ExecutionOfferId { get; init; } = default!;

    [JsonPropertyName("execution_attempt_id")]
    public string ExecutionAttemptId { get; init; } = default!;

    [JsonPropertyName("reason_code")]
    public string ReasonCode { get; init; } = default!;

    [JsonPropertyName("details")]
    public string? Details { get; init; }
}
