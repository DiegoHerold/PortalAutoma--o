namespace Biason.AutomationAgent.Domain.Models.Interactive;

public sealed class InteractiveExecutionProcessRecord
{
    public long Id { get; init; }
    public string ExecutionId { get; init; } = default!;
    public string AttemptId { get; init; } = default!;
    public int ProcessId { get; init; }
    public int? ParentProcessId { get; init; }
    public int? SessionId { get; init; }
    public string? ProcessPath { get; init; }
    public string? ProcessOwner { get; init; }
    public DateTime? StartedAtUtc { get; init; }
    public DateTime ObservedAtUtc { get; init; }
    public DateTime? ExitedAtUtc { get; set; }
    public int? ExitCode { get; set; }
    public string Kind { get; init; } = "execution_host";
    public string Status { get; set; } = "running";
}
