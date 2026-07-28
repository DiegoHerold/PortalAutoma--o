using Biason.AutomationAgent.Domain.Enums;

namespace Biason.AutomationAgent.Domain.Models;

public sealed class ExecutionRecord
{
    public string ExecutionId { get; init; } = default!;
    public ExecutionState CurrentState { get; set; }
    public ExecutionState? PreviousState { get; set; }
    public DateTime CreatedAtUtc { get; init; }
    public DateTime LastTransitionUtc { get; set; }
    public string? AutomationId { get; init; }
    public string? Reason { get; init; }
}
