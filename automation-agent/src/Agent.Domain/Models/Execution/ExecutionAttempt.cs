using Biason.AutomationAgent.Domain.Enums;

namespace Biason.AutomationAgent.Domain.Models.Execution;

public sealed class ExecutionAttempt
{
    public string AttemptId { get; init; } = default!;
    public string ExecutionId { get; init; } = default!;
    public int AttemptNumber { get; init; }
    public ExecutionState CurrentState { get; set; }
    public PoolType Pool { get; init; }
    public string? WorkspacePath { get; init; }
    public int? ProcessId { get; set; }
    public string? RuntimeId { get; init; }
    public string? PackageId { get; init; }
    public DateTime CreatedAtUtc { get; init; }
    public DateTime? StartedAtUtc { get; set; }
    public DateTime? CompletedAtUtc { get; set; }
    public int? ExitCode { get; set; }
    public string? ErrorMessage { get; set; }
    public long? PeakMemoryMb { get; set; }
    public double? CpuTimeSeconds { get; set; }
}
