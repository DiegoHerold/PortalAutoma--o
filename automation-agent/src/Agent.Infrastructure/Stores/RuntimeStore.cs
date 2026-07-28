using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Models.Storage;
using Microsoft.Extensions.Logging;

namespace Biason.AutomationAgent.Infrastructure.Stores;

public sealed class RuntimeStore : IRuntimeStore
{
    private readonly IDirectoryResolver _dirs;
    private readonly IIntegrityVerifier _verifier;
    private readonly IRuntimeArtifactRepository _repo;
    private readonly IClock _clock;
    private readonly ILogger<RuntimeStore> _logger;

    public RuntimeStore(
        IDirectoryResolver dirs,
        IIntegrityVerifier verifier,
        IRuntimeArtifactRepository repo,
        IClock clock,
        ILogger<RuntimeStore> logger)
    {
        _dirs = dirs;
        _verifier = verifier;
        _repo = repo;
        _clock = clock;
        _logger = logger;
    }

    public bool Exists(string runtimeId, string version)
    {
        var path = GetStorePath(runtimeId, version);
        return Directory.Exists(path);
    }

    public string? GetPath(string runtimeId, string version)
    {
        var path = GetStorePath(runtimeId, version);
        return Directory.Exists(path) ? path : null;
    }

    public async Task<RuntimeArtifact> ImportAsync(string runtimeId, string version, string archivePath, string sha256, CancellationToken ct = default)
    {
        // Verify hash before importing
        var valid = await _verifier.VerifySha256Async(archivePath, sha256, ct);
        if (!valid)
            throw new InvalidOperationException($"SHA-256 verification failed for runtime {runtimeId}:{version}");

        var storePath = GetStorePath(runtimeId, version);

        // Extract to store (immutable — if exists, skip)
        if (Directory.Exists(storePath))
        {
            _logger.LogInformation("Runtime {RuntimeId}:{Version} already exists, skipping import", runtimeId, version);
        }
        else
        {
            var result = await _verifier.ExtractVerifiedAsync(archivePath, storePath, ct);
            if (!result.Success)
                throw new InvalidOperationException($"Failed to extract runtime: {result.ErrorMessage}");

            _logger.LogInformation("Imported runtime {RuntimeId}:{Version} ({FileCount} files, {SizeKb}KB)",
                runtimeId, version, result.FileCount, result.ExtractedBytes / 1024);
        }

        var artifact = new RuntimeArtifact
        {
            RuntimeId = runtimeId,
            Version = version,
            Platform = "win-x64",
            Sha256 = sha256,
            SizeBytes = new FileInfo(archivePath).Length,
            StorePath = storePath,
            DownloadedAtUtc = _clock.UtcNow,
            VerifiedAtUtc = _clock.UtcNow,
            IsValid = true
        };

        await _repo.SaveAsync(artifact, ct);
        return artifact;
    }

    public Task<IReadOnlyList<RuntimeArtifact>> ListAsync(CancellationToken ct = default)
        => _repo.ListAsync(ct);

    public async Task<bool> RemoveAsync(string runtimeId, string version, CancellationToken ct = default)
    {
        var path = GetStorePath(runtimeId, version);
        if (Directory.Exists(path))
        {
            Directory.Delete(path, recursive: true);
            _logger.LogInformation("Removed runtime {RuntimeId}:{Version}", runtimeId, version);
        }
        await _repo.DeleteAsync(runtimeId, version, ct);
        return true;
    }

    private string GetStorePath(string runtimeId, string version)
        => Path.Combine(_dirs.RuntimesPath, $"{runtimeId}-{version}");
}
