using Biason.AutomationAgent.Domain.Models.Interactive;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface IApplicationProcessOwnershipRepository
{
    Task AddAsync(ApplicationProcessOwnershipRecord ownership, CancellationToken ct = default);
    Task<IReadOnlyList<ApplicationProcessOwnershipRecord>> GetAllAsync(CancellationToken ct = default);
    Task<IReadOnlyList<ApplicationProcessOwnershipRecord>> GetByAttemptAsync(string executionId, string attemptId, CancellationToken ct = default);
}
