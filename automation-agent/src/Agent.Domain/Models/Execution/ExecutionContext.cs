using Biason.AutomationAgent.Domain.Enums;

namespace Biason.AutomationAgent.Domain.Models.Execution;

/// <summary>
/// Full context needed to execute an automation, assembled by the ExecutionManager.
/// </summary>
public sealed class ExecutionContext
{
    public string ExecutionId { get; init; } = default!;
    public string AttemptId { get; init; } = default!;
    public string AutomationId { get; init; } = default!;
    public string AutomationVersionId { get; init; } = default!;
    public AutomationManifest Manifest { get; init; } = default!;
    public string WorkspacePath { get; init; } = default!;
    public string RuntimePath { get; init; } = default!;
    public string PackagePath { get; init; } = default!;
    public string? PipeName { get; init; }
    public PoolType Pool { get; init; }
    public int TimeoutSeconds { get; init; }
    public int GracefulShutdownSeconds { get; init; }
    public Dictionary<string, string> EnvironmentVariables { get; init; } = new();
    public string? InputJson { get; init; }
    public CancellationToken CancellationToken { get; init; }
}
