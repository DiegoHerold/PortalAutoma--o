namespace Biason.AutomationAgent.Domain.Models;

public sealed class InstalledSoftware
{
    public string Name { get; init; } = default!;
    public string? Version { get; init; }
    public string? ExecutablePath { get; init; }
    public string? Source { get; init; }
    public bool IsInstalled { get; init; }
}
