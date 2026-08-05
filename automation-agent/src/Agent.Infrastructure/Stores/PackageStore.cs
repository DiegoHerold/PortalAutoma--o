using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Models.Storage;
using Microsoft.Extensions.Logging;

namespace Biason.AutomationAgent.Infrastructure.Stores;

public sealed class PackageStore : IPackageStore
{
    private readonly IDirectoryResolver _dirs;
    private readonly IIntegrityVerifier _verifier;
    private readonly IPackageArtifactRepository _repo;
    private readonly IClock _clock;
    private readonly ILogger<PackageStore> _logger;

    public PackageStore(
        IDirectoryResolver dirs,
        IIntegrityVerifier verifier,
        IPackageArtifactRepository repo,
        IClock clock,
        ILogger<PackageStore> logger)
    {
        _dirs = dirs;
        _verifier = verifier;
        _repo = repo;
        _clock = clock;
        _logger = logger;
    }

    public bool Exists(string packageId) => Directory.Exists(GetStorePath(packageId));

    public string? GetPath(string packageId)
    {
        var path = GetStorePath(packageId);
        return Directory.Exists(path) ? path : null;
    }

    public Task<PackageArtifact?> GetArtifactAsync(string packageId, CancellationToken ct = default)
        => _repo.GetAsync(packageId, ct);

    public async Task<PackageArtifact> ImportAsync(string packageId, string automationId, string automationVersionId, string version, string archivePath, string sha256, CancellationToken ct = default)
    {
        var valid = await _verifier.VerifySha256Async(archivePath, sha256, ct);
        if (!valid)
            throw new InvalidOperationException($"SHA-256 verification failed for package {packageId}");

        var storePath = GetStorePath(packageId);

        if (Directory.Exists(storePath))
        {
            _logger.LogInformation("Package {PackageId} already exists, skipping import", packageId);
        }
        else
        {
            var result = await _verifier.ExtractVerifiedAsync(archivePath, storePath, ct);
            if (!result.Success)
                throw new InvalidOperationException($"Failed to extract package: {result.ErrorMessage}");
        }

        // Locate manifest
        var manifestPath = FindManifest(storePath);

        var artifact = new PackageArtifact
        {
            PackageId = packageId,
            AutomationId = automationId,
            AutomationVersionId = automationVersionId,
            Version = version,
            Sha256 = sha256,
            SizeBytes = new FileInfo(archivePath).Length,
            StorePath = storePath,
            ManifestPath = manifestPath ?? Path.Combine(storePath, "automation.json"),
            DownloadedAtUtc = _clock.UtcNow,
            VerifiedAtUtc = _clock.UtcNow,
            IsValid = true
        };

        await _repo.SaveAsync(artifact, ct);
        return artifact;
    }

    public Task<IReadOnlyList<PackageArtifact>> ListAsync(CancellationToken ct = default)
        => _repo.ListAsync(ct);

    public async Task<bool> RemoveAsync(string packageId, CancellationToken ct = default)
    {
        var path = GetStorePath(packageId);
        if (Directory.Exists(path))
            Directory.Delete(path, recursive: true);
        await _repo.DeleteAsync(packageId, ct);
        return true;
    }

    public async Task TouchLastUsedAsync(string packageId, CancellationToken ct = default)
    {
        await _repo.UpdateLastUsedAsync(packageId, DateTime.UtcNow, ct);
    }

    private string GetStorePath(string packageId)
        => Path.Combine(_dirs.PackagesPath, packageId);

    private static string? FindManifest(string dir)
    {
        // Look for automation.json or automation.yaml
        var json = Path.Combine(dir, "automation.json");
        if (File.Exists(json)) return json;
        var yaml = Path.Combine(dir, "automation.yaml");
        if (File.Exists(yaml)) return yaml;
        return null;
    }
}
