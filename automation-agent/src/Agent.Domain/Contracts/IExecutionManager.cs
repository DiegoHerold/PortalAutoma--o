using Biason.AutomationAgent.Domain.Models;
using Biason.AutomationAgent.Domain.Models.Execution;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface IExecutionManager
{
    Task<ExecutionResult> ExecuteAsync(ExecutionRecord execution, AutomationManifest manifest, string? inputJson, CancellationToken ct = default);
    Task CancelAsync(string executionId, CancellationToken ct = default);
    Task<IReadOnlyList<ExecutionRecord>> GetActiveExecutionsAsync(CancellationToken ct = default);
    Task RecoverOrphanedAsync(CancellationToken ct = default);
}
