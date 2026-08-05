namespace Biason.AutomationAgent.Domain.Enums;

public enum ArtifactStatus
{
    Pending,
    Announced,
    UploadUrlReceived,
    Uploading,
    Uploaded,
    Confirmed,
    RetryWait,
    Failed
}
