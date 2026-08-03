using System.ComponentModel.DataAnnotations;

namespace Biason.AutomationAgent.Domain.Configuration;

public sealed class LocalProtocolOptions
{
    public const string Section = "LocalProtocol";

    [Required]
    public string Version { get; init; } = "1.0";

    [Range(1024, 16 * 1024 * 1024)]
    public int MaximumMessageBytes { get; init; } = 1024 * 1024;

    [Range(5, 300)]
    public int ChallengeExpirationSeconds { get; init; } = 30;

    [Range(1, 24 * 60)]
    public int SessionTokenExpirationMinutes { get; init; } = 60;

    [Range(1, 24 * 60)]
    public int ExecutionTokenExpirationMinutes { get; init; } = 15;
}
