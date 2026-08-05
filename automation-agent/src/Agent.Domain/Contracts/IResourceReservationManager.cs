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

    /// <summary>
    /// Tenta transicionar TEMPORARY -&gt; COMMITTED (Bloco 5.5, seção 8/14).
    /// Retorna a reserva no seu estado atual após a tentativa — se o commit
    /// não venceu a corrida com a expiração, o status retornado já será
    /// Expired (a expiração é forçada nesse caminho para não deixar a reserva
    /// ambígua). Retorna null apenas se a reserva não existir.
    /// </summary>
    Task<ResourceReservation?> TryCommitAsync(string reservationId, CancellationToken ct = default);
}
