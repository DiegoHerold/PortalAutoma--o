using Biason.AutomationAgent.Domain.Models.Storage;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface IPackageStore
{
    bool Exists(string packageId);
    string? GetPath(string packageId);

    /// <summary>Metadados completos do pacote, incluindo o caminho do manifesto resolvido no import.</summary>
    Task<PackageArtifact?> GetArtifactAsync(string packageId, CancellationToken ct = default);
    Task<PackageArtifact> ImportAsync(string packageId, string automationId, string automationVersionId, string version, string archivePath, string sha256, CancellationToken ct = default);
    Task<IReadOnlyList<PackageArtifact>> ListAsync(CancellationToken ct = default);
    Task<bool> RemoveAsync(string packageId, CancellationToken ct = default);
    Task TouchLastUsedAsync(string packageId, CancellationToken ct = default);
}
