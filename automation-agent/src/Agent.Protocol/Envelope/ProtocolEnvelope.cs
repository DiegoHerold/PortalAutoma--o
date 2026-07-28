using System.Text.Json.Serialization;

namespace Biason.AutomationAgent.Protocol.Envelope;

public sealed class ProtocolEnvelope
{
    [JsonPropertyName("protocol_version")]
    public string ProtocolVersion { get; init; } = "1.0";

    [JsonPropertyName("message_id")]
    public string MessageId { get; init; } = default!;

    [JsonPropertyName("correlation_id")]
    public string? CorrelationId { get; init; }

    [JsonPropertyName("causation_id")]
    public string? CausationId { get; init; }

    [JsonPropertyName("message_type")]
    public string MessageType { get; init; } = default!;

    [JsonPropertyName("sent_at")]
    public DateTime SentAt { get; init; }

    [JsonPropertyName("agent_id")]
    public string AgentId { get; init; } = default!;

    [JsonPropertyName("agent_instance_id")]
    public string AgentInstanceId { get; init; } = default!;

    [JsonPropertyName("payload")]
    public object Payload { get; init; } = default!;

    public static ProtocolEnvelope Create(string messageType, string agentId, string instanceId, object payload)
    {
        return new ProtocolEnvelope
        {
            MessageId = $"msg_{Guid.NewGuid():N}",
            MessageType = messageType,
            SentAt = DateTime.UtcNow,
            AgentId = agentId,
            AgentInstanceId = instanceId,
            Payload = payload
        };
    }
}
