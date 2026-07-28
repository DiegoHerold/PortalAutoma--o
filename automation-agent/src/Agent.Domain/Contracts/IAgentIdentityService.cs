using Biason.AutomationAgent.Domain.Identity;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface IAgentIdentityService
{
    Task<AgentIdentity> GetOrCreateIdentityAsync(CancellationToken ct = default);
    Task<AgentIdentity?> GetIdentityAsync(CancellationToken ct = default);
    Task UpdateAgentIdAsync(string agentId, CancellationToken ct = default);

    /// <summary>Returns cached identity if already loaded, null otherwise. Non-async for hot path.</summary>
    AgentIdentity? GetCachedIdentity();
}
