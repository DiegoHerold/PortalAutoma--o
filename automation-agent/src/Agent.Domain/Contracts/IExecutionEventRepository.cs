using Biason.AutomationAgent.Domain.Models.Execution;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface IExecutionEventRepository
{
    Task SaveAsync(ExecutionEvent evt, CancellationToken ct = default);
    Task SaveBatchAsync(IEnumerable<ExecutionEvent> events, CancellationToken ct = default);
    Task<IReadOnlyList<ExecutionEvent>> GetByExecutionAsync(string executionId, CancellationToken ct = default);
    Task<IReadOnlyList<ExecutionEvent>> GetByAttemptAsync(string attemptId, CancellationToken ct = default);
}
