using Biason.AutomationAgent.Domain.Models.Sessions;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface IInteractiveSessionRepository
{
    Task UpsertAsync(InteractiveSessionRecord session, CancellationToken ct = default);
    Task<InteractiveSessionRecord?> GetAsync(int sessionId, CancellationToken ct = default);
    Task<IReadOnlyList<InteractiveSessionRecord>> GetAllAsync(CancellationToken ct = default);
    Task AttachRunnerAsync(int sessionId, string? instanceId, DateTime observedAtUtc, CancellationToken ct = default);
}
