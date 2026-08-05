using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models;
using Biason.AutomationAgent.Domain.StateMachines;

namespace Biason.AutomationAgent.Application.Execution;

/// <summary>
/// Ponto único de transição de estado de execução para os handlers de
/// comando do Portal (offer/commit/cancel/sync) — reaproveita a mesma
/// <see cref="ExecutionStateMachine"/> que o <see cref="ExecutionManager"/>
/// usa internamente, para não criar uma segunda máquina de estados
/// (Bloco 5.5, seção 2).
/// </summary>
public static class ExecutionTransitions
{
    public static async Task TransitionAsync(
        IExecutionRepository execRepo,
        IClock clock,
        ExecutionRecord exec,
        ExecutionState to,
        CancellationToken ct = default)
    {
        if (exec.CurrentState == to) return;
        ExecutionStateMachine.ValidateTransition(exec.CurrentState, to);
        exec.PreviousState = exec.CurrentState;
        exec.CurrentState = to;
        exec.LastTransitionUtc = clock.UtcNow;
        await execRepo.UpdateStateAsync(exec.ExecutionId, exec, ct);
    }
}
