using Biason.AutomationAgent.Domain.Enums;

namespace Biason.AutomationAgent.Domain.Models;

public sealed class StateTransitionRecord
{
    public long Id { get; init; }
    public string EntityType { get; init; } = default!;
    public string? EntityId { get; init; }
    public string FromState { get; init; } = default!;
    public string ToState { get; init; } = default!;
    public string? Reason { get; init; }
    public string? Details { get; init; }
    public string? Source { get; init; }
    public DateTime TransitionedAtUtc { get; init; }
}
