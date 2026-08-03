using System.ComponentModel.DataAnnotations;

namespace Biason.AutomationAgent.Domain.Configuration;

public sealed class MessagingOptions
{
    public const string Section = "Messaging";

    [Range(1, 500)]
    public int OutboxBatchSize { get; init; } = 500;

    [Range(1, 60)]
    public int PollIntervalSeconds { get; init; } = 1;

    [Range(5, 3600)]
    public int AcknowledgementTimeoutSeconds { get; init; } = 30;

    [Range(1, 100)]
    public int MaxAttempts { get; init; } = 5;

    [Range(1, 3600)]
    public int RetryDelaySeconds { get; init; } = 5;
}
