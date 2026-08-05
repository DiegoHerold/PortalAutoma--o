using Biason.AutomationAgent.Domain.Enums;

namespace Biason.AutomationAgent.Domain.Models.Capacity;

public sealed class ResourceReservation
{
    public string ReservationId { get; init; } = default!;
    public string ExecutionId { get; init; } = default!;
    public PoolType Pool { get; init; }
    public int Slots { get; init; } = 1;
    public ReservationStatus Status { get; set; } = ReservationStatus.Temporary;
    public DateTime CreatedAtUtc { get; init; }
    public DateTime ExpiresAtUtc { get; init; }
    public DateTime? ReleasedAtUtc { get; set; }
}
