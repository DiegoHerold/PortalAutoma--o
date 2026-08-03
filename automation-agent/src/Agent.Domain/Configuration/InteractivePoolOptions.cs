using System.ComponentModel.DataAnnotations;

namespace Biason.AutomationAgent.Domain.Configuration;

public sealed class InteractivePoolOptions
{
    public const string Section = "InteractivePool";

    [Range(1, 10)]
    public int GlobalSlots { get; init; } = 1;

    [Range(1, 10)]
    public int PerSessionSlots { get; init; } = 1;

    [Range(5, 3600)]
    public int LockLeaseSeconds { get; init; } = 300;
}
