namespace Biason.AutomationAgent.Domain.Contracts;

public interface IWorkspaceManager
{
    /// <summary>Create an isolated workspace directory for an execution attempt.</summary>
    string CreateWorkspace(string executionId, string attemptId);

    /// <summary>Cleanup a workspace after execution completes.</summary>
    Task CleanupAsync(string workspacePath, CancellationToken ct = default);

    /// <summary>Cleanup all stale workspaces (no active execution).</summary>
    Task CleanupStaleAsync(CancellationToken ct = default);
}
