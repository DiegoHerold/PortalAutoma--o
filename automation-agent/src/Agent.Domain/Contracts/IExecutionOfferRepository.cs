using Biason.AutomationAgent.Domain.Models.Execution;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface IExecutionOfferRepository
{
    Task SaveAsync(ExecutionOfferRecord offer, CancellationToken ct = default);
    Task<ExecutionOfferRecord?> GetByMessageIdAsync(string offerMessageId, CancellationToken ct = default);

    /// <summary>
    /// Última oferta recebida para uma tentativa — base da idempotência de
    /// seção 6 (duplicada idêntica vs. EXECUTION_ATTEMPT_CONFLICT).
    /// </summary>
    Task<ExecutionOfferRecord?> GetLatestByAttemptAsync(string executionAttemptId, CancellationToken ct = default);
    Task<IReadOnlyList<ExecutionOfferRecord>> GetRecentAsync(int limit = 100, CancellationToken ct = default);
}
