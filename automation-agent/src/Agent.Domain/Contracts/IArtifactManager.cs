using Biason.AutomationAgent.Domain.Models.Execution;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface IArtifactManager
{
    Task RegisterAsync(
        string executionId,
        string executionAttemptId,
        IReadOnlyList<ExecutionArtifactRef> artifacts,
        CancellationToken ct = default);
}
