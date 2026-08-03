namespace Biason.AutomationAgent.Domain.Models.Messaging;

public static class InboxCommandStatus
{
    public const string Pending = "pending";
    public const string Processing = "processing";
    public const string Processed = "processed";
    public const string DeadLetter = "dead_letter";
}

public sealed class InboxCommand
{
    public long Id { get; init; }
    public string MessageId { get; init; } = default!;
    public string CommandType { get; init; } = default!;
    public string PayloadJson { get; init; } = "{}";
    public string? CorrelationId { get; init; }
    public string? ExecutionId { get; init; }
    public string? ExecutionAttemptId { get; init; }
    public DateTime ReceivedAtUtc { get; init; }
    public DateTime? ProcessedAtUtc { get; init; }
    public string Status { get; init; } = InboxCommandStatus.Pending;
    public int AttemptCount { get; init; }
    public string? Result { get; init; }
    public string? Error { get; init; }
}

public sealed class InboxCommandDraft
{
    public string MessageId { get; init; } = default!;
    public string CommandType { get; init; } = default!;
    public string PayloadJson { get; init; } = "{}";
    public string? CorrelationId { get; init; }
    public string? ExecutionId { get; init; }
    public string? ExecutionAttemptId { get; init; }
    public DateTime ReceivedAtUtc { get; init; }
}

public sealed record InboxStoreResult(InboxCommand Command, bool IsDuplicate, bool PayloadMatches);
