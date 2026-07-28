using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Capacity;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface IResourceReservationManager
{
    Task<ResourceReservation> ReserveAsync(string executionId, PoolType pool, int slots, CancellationToken ct = default);
    Task ReleaseAsync(string reservationId, CancellationToken ct = default);
    Task ExpireStaleAsync(CancellationToken ct = default);
    Task<ResourceReservation?> GetAsync(string reservationId, CancellationToken ct = default);
    Task<IReadOnlyList<ResourceReservation>> GetActiveAsync(CancellationToken ct = default);
}
