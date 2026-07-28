using Biason.AutomationAgent.Domain.Models.Storage;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface IDownloadManager
{
    /// <summary>Download a file with streaming, retry, and hash verification.</summary>
    Task<DownloadResult> DownloadAsync(DownloadRequest request, CancellationToken ct = default);
}

public sealed class DownloadResult
{
    public bool Success { get; init; }
    public string? FilePath { get; init; }
    public string? ErrorMessage { get; init; }
    public long BytesDownloaded { get; init; }
    public int RetryCount { get; init; }
}
