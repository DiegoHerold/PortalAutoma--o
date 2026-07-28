using Biason.AutomationAgent.Domain.Models;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface IExecutionRepository
{
    Task SaveAsync(ExecutionRecord record, CancellationToken ct = default);
    Task<ExecutionRecord?> GetAsync(string executionId, CancellationToken ct = default);
    Task UpdateStateAsync(string executionId, ExecutionRecord record, CancellationToken ct = default);
}
