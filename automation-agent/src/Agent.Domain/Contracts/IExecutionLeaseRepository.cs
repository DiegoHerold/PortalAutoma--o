using Biason.AutomationAgent.Domain.Models.Execution;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface IExecutionLeaseRepository
{
    Task SaveAsync(ExecutionLeaseRecord lease, CancellationToken ct = default);
    Task<ExecutionLeaseRecord?> GetAsync(string leaseId, CancellationToken ct = default);
    Task<ExecutionLeaseRecord?> GetByAttemptAsync(string executionAttemptId, CancellationToken ct = default);

    /// <summary>Leases em estado não-final (active/at_risk) — usado na recuperação de boot.</summary>
    Task<IReadOnlyList<ExecutionLeaseRecord>> GetNonFinalAsync(CancellationToken ct = default);

    Task UpdateAsync(ExecutionLeaseRecord lease, CancellationToken ct = default);
}
