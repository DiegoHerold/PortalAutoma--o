using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Interactive;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface IInteractiveExecutionAssignmentRepository
{
    Task SaveAsync(InteractiveExecutionAssignment assignment, CancellationToken ct = default);
    Task<InteractiveExecutionAssignment?> GetAsync(string executionId, string attemptId, CancellationToken ct = default);
    Task<IReadOnlyList<InteractiveExecutionAssignment>> GetActiveAsync(CancellationToken ct = default);
    Task<IReadOnlyList<InteractiveExecutionAssignment>> GetAllAsync(CancellationToken ct = default);
    Task<int> CountActiveAsync(CancellationToken ct = default);
    Task<int> CountActiveBySessionAsync(int sessionId, CancellationToken ct = default);
    Task UpdateStatusAsync(string executionId, string attemptId, InteractiveExecutionStatus status, DateTime nowUtc, string? errorCode = null, string? errorMessage = null, CancellationToken ct = default);
    Task MarkStartedAsync(string executionId, string attemptId, int processId, DateTime nowUtc, CancellationToken ct = default);
    Task MarkCompletedAsync(string executionId, string attemptId, InteractiveExecutionStatus status, int? exitCode, DateTime nowUtc, string? errorCode, string? errorMessage, CancellationToken ct = default);
    Task UpdatePreparedPathsAsync(string executionId, string attemptId, string workspacePath, string runtimePath, string packagePath, CancellationToken ct = default);
}
