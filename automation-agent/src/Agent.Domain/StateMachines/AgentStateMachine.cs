using Biason.AutomationAgent.Domain.Enums;

namespace Biason.AutomationAgent.Domain.StateMachines;

public sealed class AgentStateMachine
{
    private static readonly Dictionary<AgentState, HashSet<AgentState>> AllowedTransitions = new()
    {
        [AgentState.Starting] = new() { AgentState.Initializing, AgentState.Faulted },
        [AgentState.Initializing] = new() { AgentState.Ready, AgentState.Degraded, AgentState.Faulted },
        [AgentState.Ready] = new() { AgentState.Degraded, AgentState.Draining, AgentState.Disabled, AgentState.Updating, AgentState.Stopping, AgentState.Faulted },
        [AgentState.Degraded] = new() { AgentState.Ready, AgentState.Draining, AgentState.Disabled, AgentState.Updating, AgentState.Stopping, AgentState.Faulted },
        [AgentState.Draining] = new() { AgentState.Ready, AgentState.Stopping, AgentState.Faulted },
        [AgentState.Disabled] = new() { AgentState.Ready, AgentState.Stopping, AgentState.Faulted },
        [AgentState.Updating] = new() { AgentState.Ready, AgentState.Stopping, AgentState.Faulted },
        [AgentState.Stopping] = new() { AgentState.Stopped, AgentState.Faulted },
        [AgentState.Stopped] = new(),
        [AgentState.Faulted] = new() { AgentState.Stopping, AgentState.Starting }
    };

    public static bool CanTransition(AgentState from, AgentState to)
    {
        return AllowedTransitions.TryGetValue(from, out var targets) && targets.Contains(to);
    }

    public static void ValidateTransition(AgentState from, AgentState to)
    {
        if (!CanTransition(from, to))
            throw new InvalidStateTransitionException(from.ToString(), to.ToString());
    }

    public static IReadOnlySet<AgentState> GetAllowedTransitions(AgentState from)
    {
        return AllowedTransitions.TryGetValue(from, out var targets) ? targets : new HashSet<AgentState>();
    }
}
