using Biason.AutomationAgent.Domain.Enums;

namespace Biason.AutomationAgent.Domain.Models;

public sealed class Capability
{
    public string Key { get; init; } = default!;
    public CapabilityStatus Status { get; init; }
    public string? Version { get; init; }
    public string? Source { get; init; }
    public DateTime DetectedAtUtc { get; init; }
    public Dictionary<string, string>? Details { get; init; }
}
