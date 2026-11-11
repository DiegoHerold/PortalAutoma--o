using System.Text.Json.Serialization;

namespace Biason.AutomationAgent.ExecutionHost.Protocol;

/// <summary>
/// Protocol envelope for Agent Service ↔ ExecutionHost communication via Named Pipe.
/// Protocol version 1.0.
/// </summary>
public sealed class HostMessage
{
    [JsonPropertyName("protocol_version")]
    public string ProtocolVersion { get; init; } = "1.0";

    [JsonPropertyName("message_id")]
    public string MessageId { get; init; } = Guid.NewGuid().ToString("N");

    [JsonPropertyName("message_type")]
    public string MessageType { get; init; } = default!;

    [JsonPropertyName("sent_at")]
    public DateTime SentAtUtc { get; init; } = DateTime.UtcNow;

    [JsonPropertyName("execution_id")]
    public string ExecutionId { get; init; } = default!;

    [JsonPropertyName("execution_attempt_id")]
    public string? AttemptId { get; init; }

    [JsonPropertyName("sequence")]
    public long Sequence { get; init; }

    [JsonPropertyName("payload")]
    public object? Payload { get; init; }
}

public static class MessageTypes
{
    public const string HostReady = "execution_host.ready";
    public const string Started = "execution.started";
    public const string Log = "execution.log";
    public const string Progress = "execution.progress";
    public const string Metric = "execution.metric";
    public const string Result = "execution.result";
    public const string Failed = "execution.failed";
    public const string CancellationRequested = "execution.cancellation_requested";
    public const string Cancelled = "execution.cancelled";
    public const string Heartbeat = "execution.heartbeat";
    public const string AutomationEvent = "automation.event";
}
