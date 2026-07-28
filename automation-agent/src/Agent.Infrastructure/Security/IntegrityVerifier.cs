using System.IO.Compression;
using System.Security.Cryptography;
using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Contracts;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace Biason.AutomationAgent.Infrastructure.Security;

public sealed class IntegrityVerifier : IIntegrityVerifier
{
    private readonly DownloadOptions _downloadOpts;
    private readonly SecurityOptions _securityOpts;
    private readonly ILogger<IntegrityVerifier> _logger;

    public IntegrityVerifier(
        IOptions<DownloadOptions> downloadOpts,
        IOptions<SecurityOptions> securityOpts,
        ILogger<IntegrityVerifier> logger)
    {
        _downloadOpts = downloadOpts.Value;
        _securityOpts = securityOpts.Value;
        _logger = logger;
    }

    public async Task<string> ComputeSha256Async(string filePath, CancellationToken ct = default)
    {
        using var stream = new FileStream(filePath, FileMode.Open, FileAccess.Read, FileShare.Read, 81920, true);
        var hash = await SHA256.HashDataAsync(stream, ct);
        return Convert.ToHexString(hash).ToLowerInvariant();
    }

    public async Task<bool> VerifySha256Async(string filePath, string expectedHash, CancellationToken ct = default)
    {
        var actual = await ComputeSha256Async(filePath, ct);
        var expected = expectedHash.ToLowerInvariant();
        if (actual == expected) return true;

        _logger.LogWarning("SHA-256 mismatch for {Path}: expected={Expected}, actual={Actual}",
            filePath, expected, actual);
        return false;
    }

    public async Task<IntegrityExtractionResult> ExtractVerifiedAsync(string archivePath, string destinationPath, CancellationToken ct = default)
    {
        try
        {
            // Pre-scan: check for path traversal and ZIP bomb indicators
            long compressedSize = new FileInfo(archivePath).Length;
            long totalUncompressed = 0;
            int fileCount = 0;

            using (var archive = ZipFile.OpenRead(archivePath))
            {
                foreach (var entry in archive.Entries)
                {
                    ct.ThrowIfCancellationRequested();

                    // Path traversal check
                    if (_securityOpts.BlockPathTraversal)
                    {
                        var fullPath = Path.GetFullPath(Path.Combine(destinationPath, entry.FullName));
                        var destFull = Path.GetFullPath(destinationPath + Path.DirectorySeparatorChar);
                        if (!fullPath.StartsWith(destFull, StringComparison.OrdinalIgnoreCase))
                        {
                            _logger.LogError("Path traversal detected in archive entry: {Entry}", entry.FullName);
                            return new IntegrityExtractionResult
                            {
                                Success = false,
                                ErrorMessage = $"Path traversal detected: {entry.FullName}"
                            };
                        }
                    }

                    totalUncompressed += entry.Length;
                    fileCount++;

                    // ZIP bomb: check compression ratio
                    if (compressedSize > 0 && totalUncompressed > 0)
                    {
                        double ratio = (double)totalUncompressed / compressedSize;
                        if (ratio > _downloadOpts.MaxCompressionRatio)
                        {
                            _logger.LogError("ZIP bomb detected: ratio={Ratio:F1} exceeds max={Max}",
                                ratio, _downloadOpts.MaxCompressionRatio);
                            return new IntegrityExtractionResult
                            {
                                Success = false,
                                ErrorMessage = $"Suspicious compression ratio: {ratio:F1}x (max: {_downloadOpts.MaxCompressionRatio}x)"
                            };
                        }
                    }

                    // Max extracted size
                    long maxBytes = (long)_downloadOpts.MaxExtractedSizeMb * 1024 * 1024;
                    if (totalUncompressed > maxBytes)
                    {
                        _logger.LogError("Archive exceeds max extracted size: {SizeMb}MB > {MaxMb}MB",
                            totalUncompressed / (1024 * 1024), _downloadOpts.MaxExtractedSizeMb);
                        return new IntegrityExtractionResult
                        {
                            Success = false,
                            ErrorMessage = $"Archive exceeds max extracted size: {_downloadOpts.MaxExtractedSizeMb}MB"
                        };
                    }
                }
            }

            // Actually extract
            Directory.CreateDirectory(destinationPath);
            ZipFile.ExtractToDirectory(archivePath, destinationPath, overwriteFiles: false);

            _logger.LogInformation("Extracted {FileCount} files ({SizeKb}KB) from {Archive}",
                fileCount, totalUncompressed / 1024, Path.GetFileName(archivePath));

            return new IntegrityExtractionResult
            {
                Success = true,
                ExtractedBytes = totalUncompressed,
                FileCount = fileCount
            };
        }
        catch (OperationCanceledException) { throw; }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to extract archive {Path}", archivePath);
            return new IntegrityExtractionResult
            {
                Success = false,
                ErrorMessage = ex.Message
            };
        }
    }
}
