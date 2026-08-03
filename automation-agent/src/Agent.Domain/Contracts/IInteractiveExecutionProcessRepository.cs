using Biason.AutomationAgent.Domain.Models.Interactive;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface IInteractiveExecutionProcessRepository
{
    Task AddAsync(InteractiveExecutionProcessRecord process, CancellationToken ct = default);
    Task<IReadOnlyList<InteractiveExecutionProcessRecord>> GetByAttemptAsync(string executionId, string attemptId, CancellationToken ct = default);
    Task<IReadOnlyList<InteractiveExecutionProcessRecord>> GetAllAsync(CancellationToken ct = default);
    Task MarkExitedAsync(string executionId, string attemptId, int processId, DateTime exitedAtUtc, int? exitCode, CancellationToken ct = default);
}
