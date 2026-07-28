namespace Biason.AutomationAgent.Domain.Contracts;

public interface ICacheManager
{
    Task<CacheStatus> GetStatusAsync(CancellationToken ct = default);
    Task<long> CleanupAsync(long? targetFreeMb = null, CancellationToken ct = default);
}

public sealed class CacheStatus
{
    public long RuntimeStoreSizeMb { get; init; }
    public int RuntimeCount { get; init; }
    public long PackageStoreSizeMb { get; init; }
    public int PackageCount { get; init; }
    public long DownloadsSizeMb { get; init; }
    public long TotalSizeMb => RuntimeStoreSizeMb + PackageStoreSizeMb + DownloadsSizeMb;
}
