using Biason.AutomationAgent.Domain.Enums;

namespace Biason.AutomationAgent.Domain.Models.Storage;

public sealed class DownloadRequest
{
    public string DownloadId { get; init; } = default!;
    public string Url { get; init; } = default!;
    public string TargetPath { get; init; } = default!;
    public string ExpectedSha256 { get; init; } = default!;
    public long? ExpectedSizeBytes { get; init; }
    public DownloadStatus Status { get; set; } = DownloadStatus.Pending;
    public long BytesDownloaded { get; set; }
    public int RetryCount { get; set; }
    public DateTime CreatedAtUtc { get; init; }
    public DateTime? CompletedAtUtc { get; set; }
    public string? ErrorMessage { get; set; }
}
