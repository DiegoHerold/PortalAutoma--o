namespace Biason.AutomationAgent.Domain.Enums;

public enum ExecutionState
{
    Offered,
    Reserved,
    Committed,
    Preparing,
    Starting,
    Running,
    Finalizing,
    Succeeded,
    Rejected,
    CancelRequested,
    Cancelling,
    Cancelled,
    Failed,
    TimedOut,
    Interrupted,
    Orphaned
}
