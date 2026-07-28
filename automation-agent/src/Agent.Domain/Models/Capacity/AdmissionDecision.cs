using Biason.AutomationAgent.Domain.Enums;

namespace Biason.AutomationAgent.Domain.Models.Capacity;

public sealed class AdmissionDecision
{
    public bool Accepted { get; init; }
    public string? ReservationId { get; init; }
    public string? RejectionReason { get; init; }
    public PoolType Pool { get; init; }
    public int SlotsReserved { get; init; }
}
