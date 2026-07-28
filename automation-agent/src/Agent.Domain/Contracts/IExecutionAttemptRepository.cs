using Biason.AutomationAgent.Domain.Models.Execution;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface IExecutionAttemptRepository
{
    Task SaveAsync(ExecutionAttempt attempt, CancellationToken ct = default);
    Task<ExecutionAttempt?> GetAsync(string attemptId, CancellationToken ct = default);
    Task<IReadOnlyList<ExecutionAttempt>> GetByExecutionAsync(string executionId, CancellationToken ct = default);
    Task UpdateAsync(ExecutionAttempt attempt, CancellationToken ct = default);
}
