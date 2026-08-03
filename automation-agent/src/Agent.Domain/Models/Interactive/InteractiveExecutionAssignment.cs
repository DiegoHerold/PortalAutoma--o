using Biason.AutomationAgent.Domain.Enums;

namespace Biason.AutomationAgent.Domain.Models.Interactive;

public sealed class InteractiveExecutionAssignment
{
    public string ExecutionId { get; init; } = default!;
    public string AttemptId { get; init; } = default!;
    public int SessionId { get; init; }
    public string SessionRunnerInstanceId { get; init; } = default!;
    public string? ReservationId { get; init; }
    public string? WorkspacePath { get; set; }
    public string? RuntimePath { get; set; }
    public string? PackagePath { get; set; }
    public InteractiveExecutionStatus Status { get; set; } = InteractiveExecutionStatus.Reserved;
    public DateTime CreatedAtUtc { get; init; }
    public DateTime? StartedAtUtc { get; set; }
    public DateTime? CompletedAtUtc { get; set; }
    public DateTime? LastHeartbeatAtUtc { get; set; }
    public DateTime? CancellationRequestedAtUtc { get; set; }
    public int? ExecutionHostProcessId { get; set; }
    public int? ExitCode { get; set; }
    public string? ErrorCode { get; set; }
    public string? ErrorMessage { get; set; }
}
