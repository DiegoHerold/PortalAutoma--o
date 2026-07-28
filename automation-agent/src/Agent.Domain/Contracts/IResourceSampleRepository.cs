using Biason.AutomationAgent.Domain.Models;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface IResourceSampleRepository
{
    Task SaveAsync(ResourceSample sample, CancellationToken ct = default);
    Task<IReadOnlyList<ResourceSample>> GetRecentAsync(int minutes, CancellationToken ct = default);
    Task<ResourceSample?> GetLatestAsync(CancellationToken ct = default);
    Task PurgeOlderThanAsync(DateTime cutoff, CancellationToken ct = default);
}
