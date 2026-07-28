namespace Biason.AutomationAgent.Domain.Configuration;

public sealed class DevelopmentOptions
{
    public const string Section = "Development";
    public string? DataDirectory { get; set; }
    public bool ConsoleLogging { get; set; } = true;
}
