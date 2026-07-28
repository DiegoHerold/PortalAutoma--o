using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Storage;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace Biason.AutomationAgent.Infrastructure.Downloads;

public sealed class DownloadManager : IDownloadManager
{
    private readonly HttpClient _httpClient;
    private readonly IIntegrityVerifier _verifier;
    private readonly DownloadOptions _options;
    private readonly SecurityOptions _securityOpts;
    private readonly ILogger<DownloadManager> _logger;

    public DownloadManager(
        HttpClient httpClient,
        IIntegrityVerifier verifier,
        IOptions<DownloadOptions> options,
        IOptions<SecurityOptions> securityOpts,
        ILogger<DownloadManager> logger)
    {
        _httpClient = httpClient;
        _verifier = verifier;
        _options = options.Value;
        _securityOpts = securityOpts.Value;
        _logger = logger;
    }

    public async Task<DownloadResult> DownloadAsync(DownloadRequest request, CancellationToken ct = default)
    {
        var targetDir = Path.GetDirectoryName(request.TargetPath);
        if (targetDir is not null) Directory.CreateDirectory(targetDir);

        int retryCount = 0;
        int delaySeconds = _options.InitialRetryDelaySeconds;

        while (true)
        {
            ct.ThrowIfCancellationRequested();
            try
            {
                _logger.LogInformation("Downloading {Url} (attempt {Attempt}/{Max})",
                    request.Url, retryCount + 1, _options.MaxRetries + 1);

                await DownloadStreamAsync(request, ct);

                // Verify hash
                if (_securityOpts.RequireHashVerification)
                {
                    var valid = await _verifier.VerifySha256Async(request.TargetPath, request.ExpectedSha256, ct);
                    if (!valid)
                    {
                        TryDeleteFile(request.TargetPath);
                        return new DownloadResult
                        {
                            Success = false,
                            ErrorMessage = "SHA-256 verification failed",
                            BytesDownloaded = request.BytesDownloaded,
                            RetryCount = retryCount
                        };
                    }
                }

                var fileSize = new FileInfo(request.TargetPath).Length;
                _logger.LogInformation("Download completed: {Path} ({SizeKb}KB)", request.TargetPath, fileSize / 1024);

                return new DownloadResult
                {
                    Success = true,
                    FilePath = request.TargetPath,
                    BytesDownloaded = fileSize,
                    RetryCount = retryCount
                };
            }
            catch (OperationCanceledException) { throw; }
            catch (Exception ex)
            {
                retryCount++;
                TryDeleteFile(request.TargetPath);

                if (retryCount > _options.MaxRetries)
                {
                    _logger.LogError(ex, "Download failed after {Retries} retries: {Url}", retryCount, request.Url);
                    return new DownloadResult
                    {
                        Success = false,
                        ErrorMessage = $"Failed after {retryCount} attempts: {ex.Message}",
                        RetryCount = retryCount
                    };
                }

                _logger.LogWarning(ex, "Download attempt {Attempt} failed, retrying in {Delay}s", retryCount, delaySeconds);
                await Task.Delay(TimeSpan.FromSeconds(delaySeconds), ct);
                delaySeconds = Math.Min(delaySeconds * 2, 120); // exponential backoff, max 2min
            }
        }
    }

    private async Task DownloadStreamAsync(DownloadRequest request, CancellationToken ct)
    {
        using var cts = CancellationTokenSource.CreateLinkedTokenSource(ct);
        cts.CancelAfter(TimeSpan.FromSeconds(_options.DownloadTimeoutSeconds));

        using var response = await _httpClient.GetAsync(request.Url, HttpCompletionOption.ResponseHeadersRead, cts.Token);
        response.EnsureSuccessStatusCode();

        var contentLength = response.Content.Headers.ContentLength;
        if (request.ExpectedSizeBytes.HasValue && contentLength.HasValue &&
            contentLength.Value != request.ExpectedSizeBytes.Value)
        {
            _logger.LogWarning("Content-Length mismatch: expected={Expected}, server={Server}",
                request.ExpectedSizeBytes, contentLength);
        }

        using var sourceStream = await response.Content.ReadAsStreamAsync(cts.Token);
        using var targetStream = new FileStream(request.TargetPath, FileMode.Create, FileAccess.Write, FileShare.None, _options.BufferSizeBytes, true);

        var buffer = new byte[_options.BufferSizeBytes];
        long totalBytes = 0;
        int bytesRead;

        while ((bytesRead = await sourceStream.ReadAsync(buffer, cts.Token)) > 0)
        {
            await targetStream.WriteAsync(buffer.AsMemory(0, bytesRead), cts.Token);
            totalBytes += bytesRead;
            request.BytesDownloaded = totalBytes;
        }

        await targetStream.FlushAsync(cts.Token);
    }

    private void TryDeleteFile(string path)
    {
        try { if (File.Exists(path)) File.Delete(path); }
        catch (Exception ex) { _logger.LogDebug(ex, "Failed to cleanup partial download: {Path}", path); }
    }
}
