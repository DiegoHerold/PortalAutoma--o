using System.Text.Json.Serialization;
using Biason.AutomationAgent.Protocol.Envelope;

namespace Biason.AutomationAgent.Protocol.Local;

public sealed class LocalProtocolEnvelope
{
    [JsonPropertyName("protocol_version")]
    public string ProtocolVersion { get; init; } = ProtocolConstants.CurrentVersion;

    [JsonPropertyName("message_id")]
    public string MessageId { get; init; } = NewMessageId();

    [JsonPropertyName("message_type")]
    public string MessageType { get; init; } = default!;

    [JsonPropertyName("sent_at")]
    public DateTime SentAt { get; init; } = DateTime.UtcNow;

    [JsonPropertyName("session_runner_instance_id")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public string? SessionRunnerInstanceId { get; init; }

    [JsonPropertyName("session_id")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public int? SessionId { get; init; }

    [JsonPropertyName("correlation_id")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public string? CorrelationId { get; init; }

    [JsonPropertyName("token")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public string? Token { get; init; }

    [JsonPropertyName("payload")]
    public object? Payload { get; init; }

    public static string NewMessageId() => $"local_msg_{Guid.NewGuid():N}";
}
