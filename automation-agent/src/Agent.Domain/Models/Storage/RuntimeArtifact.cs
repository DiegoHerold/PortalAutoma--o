namespace Biason.AutomationAgent.Domain.Models.Storage;

public sealed class RuntimeArtifact
{
    public string RuntimeId { get; init; } = default!;
    public string Version { get; init; } = default!;
    public string Platform { get; init; } = "win-x64";
    public string Sha256 { get; init; } = default!;
    public long SizeBytes { get; init; }
    public string StorePath { get; init; } = default!;
    public DateTime DownloadedAtUtc { get; init; }
    public DateTime? VerifiedAtUtc { get; init; }
    public bool IsValid { get; init; }
}
