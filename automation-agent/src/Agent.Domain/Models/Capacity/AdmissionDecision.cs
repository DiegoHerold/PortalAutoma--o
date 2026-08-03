using Biason.AutomationAgent.Domain.Enums;

namespace Biason.AutomationAgent.Domain.Models.Capacity;

public sealed class AdmissionDecision
{
    public bool Accepted { get; init; }
    public string? ReservationId { get; init; }
    public string? RejectionReason { get; init; }
    public string? RejectionCode { get; init; }
    public PoolType Pool { get; init; }
    public int SlotsReserved { get; init; }
    public int? SessionId { get; init; }
    public string? SessionRunnerInstanceId { get; init; }
    public string? ExecutionAttemptId { get; init; }
    public IReadOnlyList<string> ReservedLocks { get; init; } = Array.Empty<string>();
}
