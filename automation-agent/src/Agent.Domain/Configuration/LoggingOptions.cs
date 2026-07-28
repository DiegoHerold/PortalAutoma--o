namespace Biason.AutomationAgent.Domain.Configuration;

public sealed class LoggingOptions
{
    public const string Section = "AgentLogging";
    public long MaxFileSizeMb { get; set; } = 50;
    public int RetainedFileCountLimit { get; set; } = 5;
}
