using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface IAgentStateManager
{
    AgentState CurrentState { get; }
    AgentState? PreviousState { get; }
    Task TransitionToAsync(AgentState newState, string? reason = null, string? details = null, string? source = null, CancellationToken ct = default);
    Task<IReadOnlyList<StateTransitionRecord>> GetTransitionHistoryAsync(int limit = 50, CancellationToken ct = default);
}
