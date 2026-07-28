using Biason.AutomationAgent.Domain.Models.Execution;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface IResultCollector
{
    Task<ExecutionResult> CollectAsync(string executionId, string attemptId, string workspacePath, int? exitCode, CancellationToken ct = default);
}
