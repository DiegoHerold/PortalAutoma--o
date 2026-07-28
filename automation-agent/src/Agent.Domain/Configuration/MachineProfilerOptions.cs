using System.ComponentModel.DataAnnotations;

namespace Biason.AutomationAgent.Domain.Configuration;

public sealed class MachineProfilerOptions
{
    public const string Section = "MachineProfiler";

    [Range(1, 1440)]
    public int RefreshIntervalMinutes { get; set; } = 60;
}
