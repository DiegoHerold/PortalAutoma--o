using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Capacity;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface ICapacityManager
{
    CapacitySnapshot GetSnapshot();
    PoolCapacity GetPoolCapacity(PoolType pool);
    bool HasAvailableSlots(PoolType pool, int slotsNeeded = 1);
    void IncrementUsed(PoolType pool, int slots = 1);
    void DecrementUsed(PoolType pool, int slots = 1);

    /// <summary>
    /// Reconstrói `Reserved` por pool a partir das reservas persistidas
    /// (Temporary + Committed) antes do Agent aceitar novas execuções — sem
    /// isso, um restart zera a capacidade em memória enquanto o SQLite ainda
    /// tem reservas válidas, permitindo over-admission (Bloco 5.5, seção 12).
    /// Deve ser chamado no boot, depois da recuperação de execuções órfãs e
    /// da expiração de reservas stale, e antes da transição para READY.
    /// </summary>
    Task RehydrateReservationsAsync(CancellationToken ct = default);
}
