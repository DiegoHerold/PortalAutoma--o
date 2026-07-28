using System.ComponentModel.DataAnnotations;

namespace Biason.AutomationAgent.Domain.Configuration;

public sealed class CapacityOptions
{
    public const string Section = "Capacity";

    [Range(0, 50)]
    public int BackgroundPoolSize { get; init; } = 3;

    [Range(0, 10)]
    public int BrowserPoolSize { get; init; } = 1;

    [Range(0, 10)]
    public int InteractivePoolSize { get; init; } = 1;

    [Range(10, 300)]
    public int SnapshotTtlSeconds { get; init; } = 60;
}
