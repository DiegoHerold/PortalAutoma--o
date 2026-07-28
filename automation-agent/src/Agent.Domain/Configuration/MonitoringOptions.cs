using System.ComponentModel.DataAnnotations;

namespace Biason.AutomationAgent.Domain.Configuration;

public sealed class MonitoringOptions
{
    public const string Section = "Monitoring";

    [Range(1, 300)]
    public int SampleIntervalSeconds { get; set; } = 5;

    [Range(1, 10080)]
    public int HistoryRetentionMinutes { get; set; } = 60;
}
