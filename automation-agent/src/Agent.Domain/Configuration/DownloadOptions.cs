using System.ComponentModel.DataAnnotations;

namespace Biason.AutomationAgent.Domain.Configuration;

public sealed class DownloadOptions
{
    public const string Section = "Download";

    [Range(1, 10)]
    public int MaxRetries { get; init; } = 3;

    [Range(1, 60)]
    public int InitialRetryDelaySeconds { get; init; } = 2;

    [Range(30, 3600)]
    public int DownloadTimeoutSeconds { get; init; } = 600;

    [Range(1024, 1048576)]
    public int BufferSizeBytes { get; init; } = 81920;

    /// <summary>Max uncompressed/compressed ratio for ZIP bomb detection.</summary>
    [Range(2, 1000)]
    public int MaxCompressionRatio { get; init; } = 100;

    /// <summary>Max total extracted size in MB.</summary>
    [Range(100, 10240)]
    public int MaxExtractedSizeMb { get; init; } = 2048;
}
