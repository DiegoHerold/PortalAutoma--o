using Biason.AutomationAgent.Domain.Models.Sessions;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface ISessionRunnerConnectionRepository
{
    Task<long> AddAsync(SessionRunnerConnectionRecord connection, CancellationToken ct = default);
    Task MarkAuthenticatedAsync(long id, DateTime authenticatedAtUtc, CancellationToken ct = default);
    Task MarkDisconnectedAsync(long id, DateTime disconnectedAtUtc, string reason, CancellationToken ct = default);
    Task<IReadOnlyList<SessionRunnerConnectionRecord>> GetRecentAsync(int count, CancellationToken ct = default);
}
