using Biason.AutomationAgent.Domain.Models;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface ICapabilityDetector
{
    Task<IReadOnlyList<Capability>> DetectAllAsync(CancellationToken ct = default);
}
