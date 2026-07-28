namespace Biason.AutomationAgent.Domain.Identity;

public sealed class AgentIdentity
{
    public string InstallationId { get; init; } = default!;
    public string? AgentId { get; set; }
    public string MachineId { get; init; } = default!;
    public string InstanceId { get; init; } = default!;
    public DateTime CreatedAtUtc { get; init; }
    public DateTime? RegisteredAtUtc { get; set; }
}
