using System.Net;
using System.Net.Http.Headers;
using Biason.AutomationAgent.Domain.Contracts;
using Microsoft.Extensions.Logging;

namespace Biason.AutomationAgent.Infrastructure.Http;

public sealed class ArtifactContentUploader : IArtifactContentUploader
{
    private readonly HttpClient _http;
    private readonly ILogger<ArtifactContentUploader> _logger;

    public ArtifactContentUploader(HttpClient http, ILogger<ArtifactContentUploader> logger)
    {
        _http = http;
        _logger = logger;
    }

    public async Task<PortalArtifactUploadOutcome> UploadAsync(
        PortalArtifactUploadTarget target,
        string localPath,
        string contentType,
        CancellationToken ct = default)
    {
        if (!Uri.TryCreate(target.UploadUrl, UriKind.Absolute, out var uri))
            return PortalArtifactUploadOutcome.Failed("ARTIFACT_UPLOAD_URL_INVALID", "Upload URL is not absolute.", retryable: false);

        try
        {
            await using var stream = File.OpenRead(localPath);
            using var content = new StreamContent(stream);
            if (MediaTypeHeaderValue.TryParse(contentType, out var mediaType))
                content.Headers.ContentType = mediaType;

            using var request = new HttpRequestMessage(new HttpMethod(string.IsNullOrWhiteSpace(target.Method) ? "PUT" : target.Method), uri)
            {
                Content = content
            };

            ApplyHeaders(request, content, target.Headers);

            using var response = await _http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, ct);
            return response.IsSuccessStatusCode
                ? PortalArtifactUploadOutcome.Ok()
                : PortalArtifactUploadOutcome.Failed(
                    MapArtifactStatusToReason(response.StatusCode),
                    $"Upload returned {(int)response.StatusCode} {response.ReasonPhrase}.",
                    IsRetryable(response.StatusCode));
        }
        catch (OperationCanceledException) when (ct.IsCancellationRequested)
        {
            throw;
        }
        catch (OperationCanceledException ex)
        {
            _logger.LogWarning(ex, "Artifact upload timed out for local file {Path}.", localPath);
            return PortalArtifactUploadOutcome.Failed("ARTIFACT_UPLOAD_TIMEOUT", ex.Message, retryable: true);
        }
        catch (Exception ex) when (ex is IOException or HttpRequestException)
        {
            _logger.LogWarning(ex, "Artifact upload failed for local file {Path}.", localPath);
            return PortalArtifactUploadOutcome.Failed("ARTIFACT_UPLOAD_FAILED", ex.Message, retryable: true);
        }
    }

    private static void ApplyHeaders(HttpRequestMessage request, HttpContent content, IReadOnlyDictionary<string, string>? headers)
    {
        if (headers is null)
            return;

        foreach (var (name, value) in headers)
        {
            if (string.IsNullOrWhiteSpace(name))
                continue;

            if (name.StartsWith("Content-", StringComparison.OrdinalIgnoreCase))
                content.Headers.TryAddWithoutValidation(name, value);
            else
                request.Headers.TryAddWithoutValidation(name, value);
        }
    }

    private static string MapArtifactStatusToReason(HttpStatusCode status) => status switch
    {
        HttpStatusCode.NotFound => "ARTIFACT_UPLOAD_TARGET_NOT_FOUND",
        HttpStatusCode.Unauthorized or HttpStatusCode.Forbidden => "ARTIFACT_UPLOAD_UNAUTHORIZED",
        HttpStatusCode.RequestEntityTooLarge => "ARTIFACT_TOO_LARGE",
        HttpStatusCode.Conflict => "ARTIFACT_UPLOAD_CONFLICT",
        _ => "ARTIFACT_UPLOAD_HTTP_ERROR"
    };

    private static bool IsRetryable(HttpStatusCode status) =>
        status is HttpStatusCode.TooManyRequests or HttpStatusCode.RequestTimeout ||
        (int)status >= 500;
}
