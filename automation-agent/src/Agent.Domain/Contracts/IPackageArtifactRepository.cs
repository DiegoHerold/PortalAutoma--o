using Biason.AutomationAgent.Domain.Models.Storage;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface IPackageArtifactRepository
{
    Task SaveAsync(PackageArtifact artifact, CancellationToken ct = default);
    Task<PackageArtifact?> GetAsync(string packageId, CancellationToken ct = default);
    Task<IReadOnlyList<PackageArtifact>> ListAsync(CancellationToken ct = default);
    Task DeleteAsync(string packageId, CancellationToken ct = default);
    Task UpdateLastUsedAsync(string packageId, DateTime lastUsedUtc, CancellationToken ct = default);
    Task<IReadOnlyList<PackageArtifact>> GetLeastRecentlyUsedAsync(int count, CancellationToken ct = default);
}
