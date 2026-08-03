using Biason.AutomationAgent.Domain.Models.Sessions;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface ISessionEventRepository
{
    Task AddAsync(SessionEventRecord sessionEvent, CancellationToken ct = default);
    Task<IReadOnlyList<SessionEventRecord>> GetRecentAsync(int count, CancellationToken ct = default);
}
