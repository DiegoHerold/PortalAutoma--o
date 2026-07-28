namespace Biason.AutomationAgent.Domain.Models;

public sealed class OsInfo
{
    public string Name { get; init; } = default!;
    public string? Edition { get; init; }
    public string? Version { get; init; }
    public string? Build { get; init; }
    public string Architecture { get; init; } = default!;
    public string Hostname { get; init; } = default!;
    public string? DomainOrWorkgroup { get; init; }
    public long UptimeSeconds { get; init; }
    public bool IsElevated { get; init; }
    public string AgentVersion { get; init; } = default!;
}
