using Biason.AutomationAgent.Domain.Enums;

namespace Biason.AutomationAgent.Domain.Models.Execution;

public sealed class ExecutionAttempt
{
    public string AttemptId { get; init; } = default!;
    public string ExecutionId { get; init; } = default!;
    public int AttemptNumber { get; init; }
    public ExecutionState CurrentState { get; set; }
    public PoolType Pool { get; init; }
    // "set", não "init": ExecutionManager cria o registro da tentativa antes de
    // conhecer o workspace (que só existe após a criação, seção "Create workspace"),
    // e precisa atribuir depois — mesmo padrão de ProcessId logo abaixo.
    public string? WorkspacePath { get; set; }
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
