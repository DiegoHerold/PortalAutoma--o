namespace Biason.AutomationAgent.Domain.Models;

public sealed class ResourceMetrics
{
    public ResourceSample? Current { get; init; }
    public double? CpuAveragePercent { get; init; }
    public double? CpuMaxPercent { get; init; }
    public double? MemoryAveragePercent { get; init; }
    public double? MemoryMaxPercent { get; init; }
    public double? DiskAveragePercent { get; init; }
    public int SampleCount { get; init; }
    public DateTime? OldestSampleUtc { get; init; }
    public DateTime? NewestSampleUtc { get; init; }
}
