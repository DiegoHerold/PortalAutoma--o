using Biason.AutomationAgent.Domain.Models.Sessions;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface ISessionCapabilityService
{
    Task<IReadOnlyList<DynamicSessionCapability>> GetCapabilitiesAsync(CancellationToken ct = default);
}
