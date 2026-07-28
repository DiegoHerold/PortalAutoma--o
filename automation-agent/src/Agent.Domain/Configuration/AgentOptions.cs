using System.ComponentModel.DataAnnotations;

namespace Biason.AutomationAgent.Domain.Configuration;

public sealed class AgentOptions
{
    public const string Section = "Agent";

    public string? Name { get; set; }

    [AllowedValues("workstation", "dedicated", "off_hours")]
    public string Profile { get; set; } = "workstation";

    public string Version { get; set; } = "0.1.0";
}
