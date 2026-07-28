using Biason.AutomationAgent.Domain.Models;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface IMachineProfileRepository
{
    Task SaveAsync(MachineProfileSnapshot profile, CancellationToken ct = default);
    Task<MachineProfileSnapshot?> GetLatestAsync(CancellationToken ct = default);
}
