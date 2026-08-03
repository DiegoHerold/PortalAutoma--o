using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Interactive;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace Biason.AutomationAgent.Application.Interactive;

public sealed class DesktopLockManager : IDesktopLockManager
{
    private readonly IDesktopLockRepository _locks;
    private readonly IClock _clock;
    private readonly InteractivePoolOptions _options;
    private readonly ILogger<DesktopLockManager> _logger;

    public DesktopLockManager(
        IDesktopLockRepository locks,
        IClock clock,
        IOptions<InteractivePoolOptions> options,
        ILogger<DesktopLockManager> logger)
    {
        _locks = locks;
        _clock = clock;
        _options = options.Value;
        _logger = logger;
    }

    public async Task<bool> TryReserveAsync(
        string executionId,
        string attemptId,
        int sessionId,
        IEnumerable<string> lockKeys,
        CancellationToken ct = default)
    {
        var now = _clock.UtcNow;
        var expires = now.AddSeconds(_options.LockLeaseSeconds);
        var records = lockKeys
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .Select(key => new ResourceLockRecord
            {
                LockKey = key,
                OwnerExecutionId = executionId,
                OwnerAttemptId = attemptId,
                SessionId = sessionId,
                CreatedAtUtc = now,
                LeaseExpiresAtUtc = expires,
                Status = DesktopLockStatus.Reserved
            })
            .ToArray();

        var acquired = await _locks.TryAcquireAsync(records, now, ct);
        if (!acquired)
        {
            _logger.LogWarning("DESKTOP_RESOURCE_BUSY execution={ExecutionId} attempt={AttemptId} session={SessionId}",
                executionId, attemptId, sessionId);
        }

        return acquired;
    }

    public Task CommitAsync(string executionId, string attemptId, CancellationToken ct = default) =>
        _locks.CommitAsync(executionId, attemptId, _clock.UtcNow, ct);

    public Task ActivateAsync(string executionId, string attemptId, CancellationToken ct = default) =>
        _locks.ActivateAsync(executionId, attemptId, _clock.UtcNow, ct);

    public Task RenewAsync(string executionId, string attemptId, CancellationToken ct = default)
    {
        var now = _clock.UtcNow;
        return _locks.RenewAsync(executionId, attemptId, now, now.AddSeconds(_options.LockLeaseSeconds), ct);
    }

    public Task ReleaseAsync(string executionId, string attemptId, CancellationToken ct = default) =>
        _locks.ReleaseAsync(executionId, attemptId, _clock.UtcNow, ct);

    public Task<int> RecoverExpiredAsync(CancellationToken ct = default) =>
        _locks.MarkExpiredAsync(_clock.UtcNow, ct);

    public Task<IReadOnlyList<ResourceLockRecord>> GetAllAsync(CancellationToken ct = default) =>
        _locks.GetAllAsync(ct);
}
