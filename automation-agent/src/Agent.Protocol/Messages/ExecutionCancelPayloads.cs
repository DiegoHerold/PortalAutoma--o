using System.Text.Json.Serialization;

namespace Biason.AutomationAgent.Protocol.Messages;

/// <summary>
/// Payload de <c>execution.cancel_requested</c> (Portal -&gt; Agent), conforme
/// contracts/messages/portal-to-agent/execution-cancel.schema.json (o schema
/// chama a mensagem de "execution.cancel", mas o catálogo de tipos do agente
/// usa "execution.cancel_requested" — mesma forma de payload).
/// </summary>
public sealed class ExecutionCancelRequestedPayload
{
    [JsonPropertyName("execution_id")]
    public string? ExecutionId { get; init; }

    [JsonPropertyName("execution_attempt_id")]
    public string ExecutionAttemptId { get; init; } = default!;

    [JsonPropertyName("reason")]
    public string Reason { get; init; } = default!;

    [JsonPropertyName("requested_by")]
    public string? RequestedBy { get; init; }
}
