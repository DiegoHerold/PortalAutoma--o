using Biason.AutomationAgent.Domain.Enums;

namespace Biason.AutomationAgent.Domain.Models.Sessions;

public sealed class DynamicSessionCapability
{
    public string Key { get; init; } = default!;
    public CapabilityStatus Status { get; init; }
    public string Scope { get; init; } = "session";
    public int SessionId { get; init; }
    public string Source { get; init; } = "session_runner";
    public DateTime ObservedAtUtc { get; init; }
}
