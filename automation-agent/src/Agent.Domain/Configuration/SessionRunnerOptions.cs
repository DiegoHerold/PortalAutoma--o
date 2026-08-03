using System.ComponentModel.DataAnnotations;

namespace Biason.AutomationAgent.Domain.Configuration;

public sealed class SessionRunnerOptions
{
    public const string Section = "SessionRunner";

    [Required]
    public string PipeName { get; init; } = "BiasonAutomationAgent.Session.v1";

    [Range(1, 300)]
    public int HeartbeatIntervalSeconds { get; init; } = 5;

    [Range(5, 3600)]
    public int DisconnectTimeoutSeconds { get; init; } = 20;

    [Range(1, 300)]
    public int ReconnectInitialDelaySeconds { get; init; } = 1;

    [Range(1, 3600)]
    public int ReconnectMaximumDelaySeconds { get; init; } = 30;

    public bool AllowRdpSessions { get; init; } = true;

    /// <summary>When true, an active unlocked session without a runner degrades health.</summary>
    public bool ExpectRunnerForActiveSessions { get; init; } = false;

    /// <summary>Expected installed SessionRunner.exe path. Empty means AppContext.BaseDirectory/SessionRunner.exe.</summary>
    public string? ExpectedExecutablePath { get; init; }

    /// <summary>Expected local ExecutionHost.exe path used by SessionRunner for interactive attempts.</summary>
    public string? ExecutionHostPath { get; init; }
}
