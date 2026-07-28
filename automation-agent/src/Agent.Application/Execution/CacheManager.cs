using Biason.AutomationAgent.Domain.Contracts;
using Microsoft.Extensions.Logging;

namespace Biason.AutomationAgent.Application.Execution;

public sealed class CacheManager : ICacheManager
{
    private readonly IRuntimeStore _runtimeStore;
    private readonly IPackageStore _packageStore;
    private readonly IPackageArtifactRepository _packageRepo;
    private readonly IDirectoryResolver _dirs;
    private readonly IExecutionRepository _execRepo;
    private readonly ILogger<CacheManager> _logger;

    public CacheManager(
        IRuntimeStore runtimeStore,
        IPackageStore packageStore,
        IPackageArtifactRepository packageRepo,
        IDirectoryResolver dirs,
        IExecutionRepository execRepo,
        ILogger<CacheManager> logger)
    {
        _runtimeStore = runtimeStore;
        _packageStore = packageStore;
        _packageRepo = packageRepo;
        _dirs = dirs;
        _execRepo = execRepo;
        _logger = logger;
    }

    public async Task<CacheStatus> GetStatusAsync(CancellationToken ct = default)
    {
        var runtimes = await _runtimeStore.ListAsync(ct);
        var packages = await _packageStore.ListAsync(ct);

        return new CacheStatus
        {
            RuntimeStoreSizeMb = GetDirectorySizeMb(_dirs.RuntimesPath),
            RuntimeCount = runtimes.Count,
            PackageStoreSizeMb = GetDirectorySizeMb(_dirs.PackagesPath),
            PackageCount = packages.Count,
            DownloadsSizeMb = GetDirectorySizeMb(_dirs.DownloadsPath)
        };
    }

    public async Task<long> CleanupAsync(long? targetFreeMb = null, CancellationToken ct = default)
    {
        long freedBytes = 0;

        // 1. Clean stale downloads
        freedBytes += CleanStaleDownloads();

        // 2. Clean staging directory
        freedBytes += CleanStagingDirectory();

        // 3. Evict LRU packages if needed
        if (targetFreeMb.HasValue)
        {
            freedBytes += await EvictLruPackagesAsync(targetFreeMb.Value, ct);
        }

        // 4. Clean stale workspaces (older than 24h)
        freedBytes += CleanStaleWorkspaces();

        var freedMb = freedBytes / (1024 * 1024);
        _logger.LogInformation("Cache cleanup freed {FreedMb} MB", freedMb);
        return freedMb;
    }

    private long CleanStaleDownloads()
    {
        long freed = 0;
        var downloadsPath = _dirs.DownloadsPath;
        if (!Directory.Exists(downloadsPath)) return 0;

        try
        {
            var cutoff = DateTime.UtcNow.AddHours(-24);
            foreach (var file in Directory.EnumerateFiles(downloadsPath, "*.partial"))
            {
                var info = new FileInfo(file);
                if (info.LastWriteTimeUtc < cutoff)
                {
                    freed += info.Length;
                    info.Delete();
                    _logger.LogDebug("Removed stale partial download: {File}", file);
                }
            }
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Error cleaning stale downloads");
        }
        return freed;
    }

    private long CleanStagingDirectory()
    {
        long freed = 0;
        var stagingPath = _dirs.StagingPath;
        if (!Directory.Exists(stagingPath)) return 0;

        try
        {
            var cutoff = DateTime.UtcNow.AddHours(-6);
            foreach (var dir in Directory.EnumerateDirectories(stagingPath))
            {
                var info = new DirectoryInfo(dir);
                if (info.LastWriteTimeUtc < cutoff)
                {
                    var size = GetDirectorySize(dir);
                    Directory.Delete(dir, recursive: true);
                    freed += size;
                    _logger.LogDebug("Removed stale staging directory: {Dir}", dir);
                }
            }
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Error cleaning staging directory");
        }
        return freed;
    }

    private async Task<long> EvictLruPackagesAsync(long targetFreeMb, CancellationToken ct)
    {
        long freed = 0;

        // Get active execution package IDs to protect them
        var activeExecs = await _execRepo.GetActiveAsync(ct);
        var activePackageIds = new HashSet<string>(
            activeExecs
                .Where(e => e.AutomationVersionId is not null)
                .Select(e => e.AutomationVersionId!));

        // Get LRU candidates
        var candidates = await _packageRepo.GetLeastRecentlyUsedAsync(20, ct);

        foreach (var pkg in candidates)
        {
            if (ct.IsCancellationRequested) break;

            // Never evict packages in use
            if (activePackageIds.Contains(pkg.PackageId))
            {
                _logger.LogDebug("Skipping in-use package {PackageId}", pkg.PackageId);
                continue;
            }

            var currentFreeMb = GetDirectorySizeMb(_dirs.PackagesPath);
            if (freed / (1024 * 1024) >= targetFreeMb) break;

            var removed = await _packageStore.RemoveAsync(pkg.PackageId, ct);
            if (removed)
            {
                freed += pkg.SizeBytes;
                _logger.LogInformation("Evicted LRU package {PackageId}, freed {SizeMb} MB",
                    pkg.PackageId, pkg.SizeBytes / (1024 * 1024));
            }
        }

        return freed;
    }

    private long CleanStaleWorkspaces()
    {
        long freed = 0;
        var executionsPath = _dirs.ExecutionsPath;
        if (!Directory.Exists(executionsPath)) return 0;

        try
        {
            var cutoff = DateTime.UtcNow.AddHours(-24);
            foreach (var dir in Directory.EnumerateDirectories(executionsPath))
            {
                var info = new DirectoryInfo(dir);
                if (info.LastWriteTimeUtc < cutoff)
                {
                    var size = GetDirectorySize(dir);
                    try
                    {
                        Directory.Delete(dir, recursive: true);
                        freed += size;
                        _logger.LogDebug("Removed stale workspace: {Dir}", dir);
                    }
                    catch (IOException)
                    {
                        // Directory may be in use
                    }
                }
            }
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Error cleaning stale workspaces");
        }
        return freed;
    }

    private static long GetDirectorySizeMb(string path) => GetDirectorySize(path) / (1024 * 1024);

    private static long GetDirectorySize(string path)
    {
        if (!Directory.Exists(path)) return 0;
        try
        {
            return new DirectoryInfo(path)
                .EnumerateFiles("*", SearchOption.AllDirectories)
                .Sum(f => f.Length);
        }
        catch { return 0; }
    }
}
