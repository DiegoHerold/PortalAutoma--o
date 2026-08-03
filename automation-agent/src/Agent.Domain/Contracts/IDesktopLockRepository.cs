using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Interactive;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface IDesktopLockRepository
{
    Task<bool> TryAcquireAsync(IReadOnlyList<ResourceLockRecord> locks, DateTime nowUtc, CancellationToken ct = default);
    Task<IReadOnlyList<ResourceLockRecord>> GetAllAsync(CancellationToken ct = default);
    Task<IReadOnlyList<ResourceLockRecord>> GetByOwnerAsync(string executionId, string attemptId, CancellationToken ct = default);
    Task CommitAsync(string executionId, string attemptId, DateTime nowUtc, CancellationToken ct = default);
    Task ActivateAsync(string executionId, string attemptId, DateTime nowUtc, CancellationToken ct = default);
    Task RenewAsync(string executionId, string attemptId, DateTime nowUtc, DateTime leaseExpiresAtUtc, CancellationToken ct = default);
    Task ReleaseAsync(string executionId, string attemptId, DateTime nowUtc, CancellationToken ct = default);
    Task<int> MarkExpiredAsync(DateTime nowUtc, CancellationToken ct = default);
}
