using System.Text.Json.Serialization;

namespace Biason.AutomationAgent.Protocol.Messages;

public sealed class MessageAcknowledgementPayload
{
    [JsonPropertyName("message_id")]
    public string? MessageId { get; init; }

    [JsonPropertyName("message_ids")]
    public IReadOnlyList<string>? MessageIds { get; init; }

    [JsonPropertyName("execution_attempt_id")]
    public string? ExecutionAttemptId { get; init; }

    [JsonPropertyName("last_contiguous_sequence")]
    public long? LastContiguousSequence { get; init; }

    [JsonPropertyName("status")]
    public string Status { get; init; } = "acknowledged";

    [JsonPropertyName("detail")]
    public string? Detail { get; init; }
}

public sealed class CommandAcknowledgementPayload
{
    [JsonPropertyName("message_id")]
    public string MessageId { get; init; } = default!;

    [JsonPropertyName("command_type")]
    public string CommandType { get; init; } = default!;

    [JsonPropertyName("status")]
    public string Status { get; init; } = default!;

    [JsonPropertyName("duplicate")]
    public bool Duplicate { get; init; }

    [JsonPropertyName("detail")]
    public string? Detail { get; init; }
}
