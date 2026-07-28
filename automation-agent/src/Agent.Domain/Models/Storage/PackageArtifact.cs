namespace Biason.AutomationAgent.Domain.Models.Storage;

public sealed class PackageArtifact
{
    public string PackageId { get; init; } = default!;
    public string AutomationId { get; init; } = default!;
    public string AutomationVersionId { get; init; } = default!;
    public string Version { get; init; } = default!;
    public string Sha256 { get; init; } = default!;
    public long SizeBytes { get; init; }
    public string StorePath { get; init; } = default!;
    public string ManifestPath { get; init; } = default!;
    public DateTime DownloadedAtUtc { get; init; }
    public DateTime? VerifiedAtUtc { get; init; }
    public DateTime? LastUsedAtUtc { get; set; }
    public bool IsValid { get; init; }
}
