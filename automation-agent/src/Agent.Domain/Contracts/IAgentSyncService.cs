namespace Biason.AutomationAgent.Domain.Contracts;

public interface IAgentSyncService
{
    Task PublishSyncStateAsync(string reason, string? correlationId = null, CancellationToken ct = default);
}
