using System.ComponentModel.DataAnnotations;

namespace Biason.AutomationAgent.Domain.Configuration;

public sealed class ExecutionOptions
{
    public const string Section = "Execution";

    [Range(30, 86400)]
    public int DefaultTimeoutSeconds { get; init; } = 3600;

    [Range(5, 300)]
    public int GracefulShutdownSeconds { get; init; } = 30;

    [Range(1, 100)]
    public int MaxConcurrentExecutions { get; init; } = 5;

    [Range(60, 3600)]
    public int ReservationTimeoutSeconds { get; init; } = 300;

    public bool RequirePackageSignature { get; init; } = false; // true in production
}
