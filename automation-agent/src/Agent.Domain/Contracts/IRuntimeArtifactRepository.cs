using Biason.AutomationAgent.Domain.Models.Storage;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface IRuntimeArtifactRepository
{
    Task SaveAsync(RuntimeArtifact artifact, CancellationToken ct = default);
    Task<RuntimeArtifact?> GetAsync(string runtimeId, string version, CancellationToken ct = default);
    Task<IReadOnlyList<RuntimeArtifact>> ListAsync(CancellationToken ct = default);
    Task DeleteAsync(string runtimeId, string version, CancellationToken ct = default);
}
