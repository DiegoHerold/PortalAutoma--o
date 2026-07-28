namespace Biason.AutomationAgent.Domain.Configuration;

public sealed class DatabaseOptions
{
    public const string Section = "Database";
    public int BusyTimeoutMs { get; set; } = 5000;
    public string JournalMode { get; set; } = "WAL";
}
