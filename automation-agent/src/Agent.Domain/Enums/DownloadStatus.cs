namespace Biason.AutomationAgent.Domain.Enums;

public enum DownloadStatus
{
    Pending,
    Downloading,
    Verifying,
    Extracting,
    Completed,
    Failed,
    Cancelled
}
