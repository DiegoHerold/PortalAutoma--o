using Biason.AutomationAgent.Domain.Models.Interactive;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface IInteractiveExecutionScreenshotRepository
{
    Task AddAsync(InteractiveExecutionScreenshotRecord screenshot, CancellationToken ct = default);
    Task<int> CountByAttemptAsync(string executionId, string attemptId, CancellationToken ct = default);
    Task<IReadOnlyList<InteractiveExecutionScreenshotRecord>> GetByAttemptAsync(string executionId, string attemptId, CancellationToken ct = default);
    Task<IReadOnlyList<InteractiveExecutionScreenshotRecord>> GetAllAsync(CancellationToken ct = default);
}
