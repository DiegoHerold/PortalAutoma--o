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

    /// <summary>
    /// Transição atômica TEMPORARY -&gt; COMMITTED, condicionada a status = Temporary
    /// e ainda não expirada. Retorna false se a linha não bateu a condição (já
    /// commitada, expirada, liberada, cancelada, ou TTL já vencido) — é a
    /// proteção compare-and-set contra a race commit-vs-expiração (Bloco 5.5,
    /// seção 15). Implementações devem fazer isso em uma única instrução SQL.
    /// </summary>
    Task<bool> TryCommitAsync(string reservationId, DateTime nowUtc, CancellationToken ct = default);

    /// <summary>
    /// Transição atômica TEMPORARY -&gt; EXPIRED, condicionada a status = Temporary
    /// e expires_at_utc &lt;= nowUtc. Mesma proteção compare-and-set que
    /// <see cref="TryCommitAsync"/>, usada tanto pelo serviço periódico de
    /// expiração quanto pelo commit tardio (que força a expiração explícita
    /// em vez de deixar a reserva ambígua).
    /// </summary>
    Task<bool> TryExpireAsync(string reservationId, DateTime nowUtc, CancellationToken ct = default);
}
