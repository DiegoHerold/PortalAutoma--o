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
}
