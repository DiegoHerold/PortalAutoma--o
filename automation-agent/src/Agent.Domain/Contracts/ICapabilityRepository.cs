using Biason.AutomationAgent.Domain.Models;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface ICapabilityRepository
{
    Task SaveAllAsync(IReadOnlyList<Capability> capabilities, CancellationToken ct = default);
    Task<IReadOnlyList<Capability>> GetAllAsync(CancellationToken ct = default);
}
