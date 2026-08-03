using System.ComponentModel.DataAnnotations;

namespace Biason.AutomationAgent.Domain.Configuration;

public sealed class InteractiveSessionsOptions
{
    public const string Section = "InteractiveSessions";

    [Required]
    public string DefaultSelectionPolicy { get; init; } = "active_unlocked";
}
