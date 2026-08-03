namespace Biason.AutomationAgent.Domain.Models.Interactive;

public sealed class ApplicationProcessOwnershipRecord
{
    public long Id { get; init; }
    public string ExecutionId { get; init; } = default!;
    public string AttemptId { get; init; } = default!;
    public string ApplicationKey { get; init; } = default!;
    public int ProcessId { get; init; }
    public int? SessionId { get; init; }
    public string? ProcessPath { get; init; }
    public string? WindowTitle { get; init; }
    public DateTime? StartedAtUtc { get; init; }
    public DateTime ObservedAtUtc { get; init; }
    public string OwnershipKind { get; init; } = "created";
    public string Policy { get; init; } = default!;
    public string Status { get; set; } = "owned";
}
