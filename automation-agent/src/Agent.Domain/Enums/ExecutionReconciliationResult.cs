namespace Biason.AutomationAgent.Domain.Enums;

public enum ExecutionReconciliationResult
{
    InSync,
    LocalAhead,
    RemoteAhead,
    Conflict,
    Recovered,
    RequiresIntervention
}
