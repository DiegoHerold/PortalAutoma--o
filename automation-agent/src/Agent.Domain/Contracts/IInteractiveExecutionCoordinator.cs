using Biason.AutomationAgent.Domain.Models;
using Biason.AutomationAgent.Domain.Models.Execution;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface IInteractiveExecutionCoordinator
{
    Task<ExecutionResult> ExecuteAsync(
        ExecutionRecord execution,
        AutomationManifest manifest,
        string attemptId,
        string? inputJson,
        CancellationToken ct = default);

    Task CancelAsync(string executionId, CancellationToken ct = default);
}
