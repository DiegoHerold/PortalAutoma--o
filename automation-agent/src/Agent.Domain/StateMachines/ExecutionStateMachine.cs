using Biason.AutomationAgent.Domain.Enums;

namespace Biason.AutomationAgent.Domain.StateMachines;

public sealed class ExecutionStateMachine
{
    private static readonly Dictionary<ExecutionState, HashSet<ExecutionState>> AllowedTransitions = new()
    {
        [ExecutionState.Offered] = new() { ExecutionState.Reserved, ExecutionState.Rejected },
        [ExecutionState.Reserved] = new() { ExecutionState.Committed, ExecutionState.Rejected, ExecutionState.Cancelled },
        [ExecutionState.Committed] = new() { ExecutionState.Preparing, ExecutionState.Failed, ExecutionState.Cancelled },
        [ExecutionState.Preparing] = new() { ExecutionState.Starting, ExecutionState.Failed, ExecutionState.Cancelled },
        [ExecutionState.Starting] = new() { ExecutionState.Running, ExecutionState.Failed, ExecutionState.Cancelled },
        [ExecutionState.Running] = new() { ExecutionState.Finalizing, ExecutionState.Succeeded, ExecutionState.Failed, ExecutionState.CancelRequested, ExecutionState.TimedOut, ExecutionState.Interrupted },
        [ExecutionState.Finalizing] = new() { ExecutionState.Succeeded, ExecutionState.Failed },
        [ExecutionState.CancelRequested] = new() { ExecutionState.Cancelling },
        [ExecutionState.Cancelling] = new() { ExecutionState.Cancelled, ExecutionState.Failed },
        [ExecutionState.Succeeded] = new(),
        [ExecutionState.Rejected] = new(),
        [ExecutionState.Cancelled] = new(),
        [ExecutionState.Failed] = new(),
        [ExecutionState.TimedOut] = new(),
        [ExecutionState.Interrupted] = new() { ExecutionState.Orphaned },
        [ExecutionState.Orphaned] = new()
    };

    public static bool CanTransition(ExecutionState from, ExecutionState to)
    {
        return AllowedTransitions.TryGetValue(from, out var targets) && targets.Contains(to);
    }

    public static void ValidateTransition(ExecutionState from, ExecutionState to)
    {
        if (!CanTransition(from, to))
            throw new InvalidStateTransitionException(from.ToString(), to.ToString());
    }

    public static bool IsTerminal(ExecutionState state)
    {
        return state is ExecutionState.Succeeded or ExecutionState.Rejected or ExecutionState.Cancelled
            or ExecutionState.Failed or ExecutionState.TimedOut or ExecutionState.Orphaned;
    }

    public static IReadOnlySet<ExecutionState> GetAllowedTransitions(ExecutionState from)
    {
        return AllowedTransitions.TryGetValue(from, out var targets) ? targets : new HashSet<ExecutionState>();
    }
}
