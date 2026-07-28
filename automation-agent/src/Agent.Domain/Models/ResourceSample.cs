namespace Biason.AutomationAgent.Domain.Models;

public sealed class ResourceSample
{
    public long Id { get; init; }
    public DateTime SampledAtUtc { get; init; }
    public double CpuUsagePercent { get; init; }
    public long MemoryTotalMb { get; init; }
    public long MemoryAvailableMb { get; init; }
    public long MemoryUsedMb { get; init; }
    public double MemoryUsagePercent { get; init; }
    public long DiskTotalMb { get; init; }
    public long DiskFreeMb { get; init; }
    public double DiskUsagePercent { get; init; }
    public long AgentMemoryMb { get; init; }
    public int ProcessCount { get; init; }
    public long UptimeSeconds { get; init; }
    public long DatabaseSizeKb { get; init; }
    public long LogsSizeKb { get; init; }
    public long SpoolSizeKb { get; init; }
    public long CacheSizeKb { get; init; }
    public string? SessionStatus { get; init; }
}
