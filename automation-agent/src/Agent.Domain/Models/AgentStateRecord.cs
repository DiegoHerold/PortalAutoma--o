using Biason.AutomationAgent.Domain.Enums;

namespace Biason.AutomationAgent.Domain.Models;

public sealed class AgentStateRecord
{
    public AgentState CurrentState { get; set; }
    public AgentState? PreviousState { get; set; }
    public DateTime LastTransitionUtc { get; set; }
    public string? Reason { get; set; }
    public string? Details { get; set; }
}
