namespace Biason.AutomationAgent.Domain.Enums;

public enum InteractiveExecutionStatus
{
    Reserved,
    Preparing,
    Starting,
    Running,
    CancelRequested,
    Cancelling,
    Completed,
    Failed,
    Cancelled,
    TimedOut,
    Interrupted
}
