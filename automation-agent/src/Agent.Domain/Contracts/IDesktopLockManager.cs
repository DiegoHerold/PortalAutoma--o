using Biason.AutomationAgent.Domain.Models.Interactive;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface IDesktopLockManager
{
    Task<bool> TryReserveAsync(
        string executionId,
        string attemptId,
        int sessionId,
        IEnumerable<string> lockKeys,
        CancellationToken ct = default);

    Task CommitAsync(string executionId, string attemptId, CancellationToken ct = default);
    Task ActivateAsync(string executionId, string attemptId, CancellationToken ct = default);
    Task RenewAsync(string executionId, string attemptId, CancellationToken ct = default);
    Task ReleaseAsync(string executionId, string attemptId, CancellationToken ct = default);
    Task<int> RecoverExpiredAsync(CancellationToken ct = default);
    Task<IReadOnlyList<ResourceLockRecord>> GetAllAsync(CancellationToken ct = default);
}
