namespace Biason.AutomationAgent.Domain.Enums;

public enum AgentState
{
    Starting,
    Initializing,
    Ready,
    Degraded,
    Draining,
    Disabled,
    Updating,
    Stopping,
    Stopped,
    Faulted
}
