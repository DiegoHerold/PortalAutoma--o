namespace Biason.AutomationAgent.Domain.Contracts;

public interface IInteractivePoolService
{
    Task<bool> HasSlotAsync(int sessionId, CancellationToken ct = default);
    Task<int> CountActiveAsync(CancellationToken ct = default);
    Task<int> CountActiveBySessionAsync(int sessionId, CancellationToken ct = default);
}
