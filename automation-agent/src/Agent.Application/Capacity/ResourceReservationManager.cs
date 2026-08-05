using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Capacity;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace Biason.AutomationAgent.Application.Capacity;

public sealed class ResourceReservationManager : IResourceReservationManager
{
    private readonly IReservationRepository _repo;
    private readonly ICapacityManager _capacity;
    private readonly IClock _clock;
    private readonly ExecutionOptions _execOpts;
    private readonly ILogger<ResourceReservationManager> _logger;
    private readonly object _lock = new();

    public ResourceReservationManager(
        IReservationRepository repo,
        ICapacityManager capacity,
        IClock clock,
        IOptions<ExecutionOptions> execOpts,
        ILogger<ResourceReservationManager> logger)
    {
        _repo = repo;
        _capacity = capacity;
        _clock = clock;
        _execOpts = execOpts.Value;
        _logger = logger;
    }

    public async Task<ResourceReservation> ReserveAsync(string executionId, PoolType pool, int slots, CancellationToken ct = default)
    {
        lock (_lock)
        {
            if (!_capacity.HasAvailableSlots(pool, slots))
                throw new InvalidOperationException($"No available slots in pool {pool} (requested {slots})");

            // Increment reserved in capacity (we track reserved separate from used)
            var poolCap = _capacity.GetPoolCapacity(pool);
            poolCap.Reserved += slots;
        }

        var reservation = new ResourceReservation
        {
            ReservationId = $"rsv_{Guid.NewGuid():N}",
            ExecutionId = executionId,
            Pool = pool,
            Slots = slots,
            Status = ReservationStatus.Temporary,
            CreatedAtUtc = _clock.UtcNow,
            ExpiresAtUtc = _clock.UtcNow.AddSeconds(_execOpts.ReservationTimeoutSeconds)
        };

        await _repo.SaveAsync(reservation, ct);
        _logger.LogInformation("Created reservation {ReservationId} for execution {ExecutionId} in pool {Pool} ({Slots} slots)",
            reservation.ReservationId, executionId, pool, slots);

        return reservation;
    }

    public async Task ReleaseAsync(string reservationId, CancellationToken ct = default)
    {
        var reservation = await _repo.GetAsync(reservationId, ct);
        if (reservation is null ||
            (reservation.Status != ReservationStatus.Temporary && reservation.Status != ReservationStatus.Committed))
        {
            return;
        }

        await _repo.UpdateStatusAsync(reservationId, ReservationStatus.Released, _clock.UtcNow, ct);

        lock (_lock)
        {
            var poolCap = _capacity.GetPoolCapacity(reservation.Pool);
            poolCap.Reserved = Math.Max(0, poolCap.Reserved - reservation.Slots);
        }

        _logger.LogInformation("Released reservation {ReservationId}", reservationId);
    }

    public async Task ExpireStaleAsync(CancellationToken ct = default)
    {
        var now = _clock.UtcNow;
        var expired = await _repo.GetExpiredAsync(now, ct);
        foreach (var reservation in expired)
        {
            // Compare-and-set: só decrementa a capacidade em memória se a
            // transição realmente aconteceu agora (protege contra a mesma
            // reserva já ter sido commitada/expirada por outro caminho
            // concorrente — Bloco 5.5, seção 15).
            var expiredNow = await _repo.TryExpireAsync(reservation.ReservationId, now, ct);
            if (!expiredNow) continue;

            lock (_lock)
            {
                var poolCap = _capacity.GetPoolCapacity(reservation.Pool);
                poolCap.Reserved = Math.Max(0, poolCap.Reserved - reservation.Slots);
            }
            _logger.LogWarning("Expired reservation {ReservationId} for execution {ExecutionId}", reservation.ReservationId, reservation.ExecutionId);
        }
    }

    public async Task<ResourceReservation?> TryCommitAsync(string reservationId, CancellationToken ct = default)
    {
        var now = _clock.UtcNow;
        var committed = await _repo.TryCommitAsync(reservationId, now, ct);
        if (committed)
        {
            _logger.LogInformation("Committed reservation {ReservationId}", reservationId);
            return await _repo.GetAsync(reservationId, ct);
        }

        // Não commitou: pode já estar Committed/Released/Cancelled/Expired, ou
        // ainda Temporary porém com TTL vencido (o serviço periódico de
        // expiração ainda não passou por ela). Neste último caso, força a
        // expiração agora mesmo pela mesma via compare-and-set, para que o
        // commit tardio veja um estado terminal e não uma reserva ambígua.
        var reservation = await _repo.GetAsync(reservationId, ct);
        if (reservation is not null && reservation.Status == ReservationStatus.Temporary && reservation.ExpiresAtUtc <= now)
        {
            var expiredNow = await _repo.TryExpireAsync(reservationId, now, ct);
            if (expiredNow)
            {
                lock (_lock)
                {
                    var poolCap = _capacity.GetPoolCapacity(reservation.Pool);
                    poolCap.Reserved = Math.Max(0, poolCap.Reserved - reservation.Slots);
                }
                _logger.LogWarning("Reservation {ReservationId} expired at commit time (race with expiration).", reservationId);
                return await _repo.GetAsync(reservationId, ct);
            }
        }

        return reservation;
    }

    public Task<ResourceReservation?> GetAsync(string reservationId, CancellationToken ct = default)
        => _repo.GetAsync(reservationId, ct);

    public Task<IReadOnlyList<ResourceReservation>> GetActiveAsync(CancellationToken ct = default)
        => _repo.GetActiveAsync(ct);
}
