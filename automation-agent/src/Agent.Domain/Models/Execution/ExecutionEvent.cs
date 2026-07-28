namespace Biason.AutomationAgent.Domain.Models.Execution;

public sealed class ExecutionEvent
{
    public long Id { get; init; }
    public string ExecutionId { get; init; } = default!;
    public string AttemptId { get; init; } = default!;
    public string EventType { get; init; } = default!;
    public string? Message { get; init; }
    public string? DataJson { get; init; }
    public DateTime OccurredAtUtc { get; init; }
}
