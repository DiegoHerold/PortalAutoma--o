using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface IExecutionRepository
{
    Task SaveAsync(ExecutionRecord record, CancellationToken ct = default);
    Task<ExecutionRecord?> GetAsync(string executionId, CancellationToken ct = default);
    Task UpdateStateAsync(string executionId, ExecutionRecord record, CancellationToken ct = default);
    Task<IReadOnlyList<ExecutionRecord>> GetByStateAsync(ExecutionState state, CancellationToken ct = default);
    Task<IReadOnlyList<ExecutionRecord>> GetActiveAsync(CancellationToken ct = default);
    Task<IReadOnlyList<ExecutionRecord>> GetByPoolAsync(PoolType pool, CancellationToken ct = default);
    Task<int> CountByStateAsync(ExecutionState state, CancellationToken ct = default);
}
