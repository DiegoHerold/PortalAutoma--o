namespace Biason.AutomationAgent.Domain.Models.Messaging;

public static class OutboxMessageStatus
{
    public const string Pending = "pending";
    public const string Failed = "failed";
    public const string Sent = "sent";
    public const string Acknowledged = "acknowledged";
    public const string DeadLetter = "dead_letter";
}

public sealed class OutboxMessage
{
    public long Id { get; init; }
    public string MessageId { get; init; } = default!;
    public string MessageType { get; init; } = default!;
    public string PayloadJson { get; init; } = "{}";
    public string? AgentId { get; init; }
    public string? ExecutionId { get; init; }
    public string? ExecutionAttemptId { get; init; }
    public long? Sequence { get; init; }
    public DateTime CreatedAtUtc { get; init; }
    public DateTime? AvailableAtUtc { get; init; }
    public DateTime? SentAtUtc { get; init; }
    public DateTime? AcknowledgedAtUtc { get; init; }
    public int AttemptCount { get; init; }
    public string Status { get; init; } = OutboxMessageStatus.Pending;
    public int PayloadSizeBytes { get; init; }
    public string? LastError { get; init; }
}

public sealed class OutboxMessageDraft
{
    public string MessageId { get; init; } = default!;
    public string MessageType { get; init; } = default!;
    public string PayloadJson { get; init; } = "{}";
    public string? AgentId { get; init; }
    public string? ExecutionId { get; init; }
    public string? ExecutionAttemptId { get; init; }
    public long? Sequence { get; init; }
    public DateTime CreatedAtUtc { get; init; }
    public DateTime AvailableAtUtc { get; init; }
    public string Status { get; init; } = OutboxMessageStatus.Pending;
    public int PayloadSizeBytes { get; init; }
    public string? LastError { get; init; }
}
