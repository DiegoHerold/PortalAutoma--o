namespace Biason.AutomationAgent.Domain.Models;

public sealed class CpuInfo
{
    public string? Manufacturer { get; init; }
    public string Model { get; init; } = default!;
    public string Architecture { get; init; } = default!;
    public int PhysicalCores { get; init; }
    public int LogicalProcessors { get; init; }
    public int? FrequencyMhz { get; init; }
}
