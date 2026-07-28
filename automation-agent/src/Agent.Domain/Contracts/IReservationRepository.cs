using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Capacity;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface IReservationRepository
{
    Task SaveAsync(ResourceReservation reservation, CancellationToken ct = default);
    Task<ResourceReservation?> GetAsync(string reservationId, CancellationToken ct = default);
    Task<IReadOnlyList<ResourceReservation>> GetActiveAsync(CancellationToken ct = default);
    Task<IReadOnlyList<ResourceReservation>> GetExpiredAsync(DateTime now, CancellationToken ct = default);
    Task UpdateStatusAsync(string reservationId, ReservationStatus status, DateTime? releasedAt, CancellationToken ct = default);
    Task<int> CountActiveByPoolAsync(PoolType pool, CancellationToken ct = default);
}
