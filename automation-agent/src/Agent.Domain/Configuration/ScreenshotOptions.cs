using System.ComponentModel.DataAnnotations;

namespace Biason.AutomationAgent.Domain.Configuration;

public sealed class ScreenshotOptions
{
    public const string Section = "Screenshots";

    public bool Enabled { get; init; } = true;
    public bool OnFailure { get; init; } = true;
    public bool OnTimeout { get; init; } = true;
    public bool OnCancel { get; init; } = true;

    [Range(0, 100)]
    public int MaximumPerExecution { get; init; } = 10;

    [Range(1, 100)]
    public int MaximumSizeMb { get; init; } = 10;
}
