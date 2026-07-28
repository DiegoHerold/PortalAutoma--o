namespace Biason.AutomationAgent.Domain.Contracts;

public interface IIntegrityVerifier
{
    /// <summary>Compute SHA-256 hash of a file.</summary>
    Task<string> ComputeSha256Async(string filePath, CancellationToken ct = default);

    /// <summary>Verify a file's SHA-256 matches the expected hash.</summary>
    Task<bool> VerifySha256Async(string filePath, string expectedHash, CancellationToken ct = default);

    /// <summary>Validate and extract a ZIP archive with security checks (path traversal, ZIP bomb).</summary>
    Task<IntegrityExtractionResult> ExtractVerifiedAsync(string archivePath, string destinationPath, CancellationToken ct = default);
}

public sealed class IntegrityExtractionResult
{
    public bool Success { get; init; }
    public string? ErrorMessage { get; init; }
    public long ExtractedBytes { get; init; }
    public int FileCount { get; init; }
}
