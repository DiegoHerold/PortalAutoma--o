using Biason.AutomationAgent.Domain.Models.Storage;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface IRuntimeStore
{
    /// <summary>Check if a runtime version is available locally.</summary>
    bool Exists(string runtimeId, string version);

    /// <summary>Get the path to an installed runtime.</summary>
    string? GetPath(string runtimeId, string version);

    /// <summary>Import a verified runtime archive.</summary>
    Task<RuntimeArtifact> ImportAsync(string runtimeId, string version, string archivePath, string sha256, CancellationToken ct = default);

    /// <summary>List all installed runtimes.</summary>
    Task<IReadOnlyList<RuntimeArtifact>> ListAsync(CancellationToken ct = default);

    /// <summary>Remove a runtime version.</summary>
    Task<bool> RemoveAsync(string runtimeId, string version, CancellationToken ct = default);
}
