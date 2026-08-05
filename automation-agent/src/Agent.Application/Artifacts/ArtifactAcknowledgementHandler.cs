using System.Text.Json;
using System.Globalization;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Execution;
using Biason.AutomationAgent.Domain.Models.Messaging;
using Biason.AutomationAgent.Protocol.Messages;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace Biason.AutomationAgent.Application.Artifacts;

public sealed class ArtifactAcknowledgementHandler : IArtifactAcknowledgementHandler
{
    private readonly IPendingArtifactRepository _artifacts;
    private readonly ExecutionOptions _options;
    private readonly ILogger<ArtifactAcknowledgementHandler> _logger;

    public ArtifactAcknowledgementHandler(
        IPendingArtifactRepository artifacts,
        ILogger<ArtifactAcknowledgementHandler> logger,
        IOptions<ExecutionOptions>? options = null)
    {
        _artifacts = artifacts;
        _options = options?.Value ?? new ExecutionOptions();
        _logger = logger;
    }

    public async Task HandleAsync(
        OutboxMessage originalMessage,
        MessageAcknowledgementPayload acknowledgement,
        DateTime nowUtc,
        CancellationToken ct = default)
    {
        if (acknowledgement.Ok is false)
            return;

        if (originalMessage.MessageType == PortalMessageTypes.ExecutionArtifactCreated)
        {
            await HandleCreatedAckAsync(originalMessage, acknowledgement, nowUtc, ct);
            return;
        }

        if (originalMessage.MessageType == PortalMessageTypes.ArtifactUploaded)
            await HandleUploadedAckAsync(originalMessage, acknowledgement, nowUtc, ct);
    }

    private async Task HandleCreatedAckAsync(
        OutboxMessage originalMessage,
        MessageAcknowledgementPayload acknowledgement,
        DateTime nowUtc,
        CancellationToken ct)
    {
        var artifactId = TryReadString(originalMessage.PayloadJson, "artifact_id");
        if (string.IsNullOrWhiteSpace(artifactId))
            return;

        var artifact = await _artifacts.GetAsync(artifactId, ct);
        if (artifact is null or { Status: ArtifactStatus.Confirmed or ArtifactStatus.Failed })
            return;

        if (artifact.Status is ArtifactStatus.UploadUrlReceived or ArtifactStatus.Uploading or ArtifactStatus.Uploaded &&
            !string.IsNullOrWhiteSpace(artifact.UploadUrl) &&
            !string.IsNullOrWhiteSpace(artifact.UploadSessionId))
            return;

        var result = acknowledgement.Result;
        if (result.ValueKind is JsonValueKind.Undefined or JsonValueKind.Null)
        {
            _logger.LogWarning("Artifact {ArtifactId} created ACK did not include upload instructions.", artifactId);
            return;
        }

        var uploadUrl = TryReadString(result, "upload_url");
        var uploadSessionId = TryReadString(result, "upload_session_id");
        if (string.IsNullOrWhiteSpace(uploadUrl) || string.IsNullOrWhiteSpace(uploadSessionId))
        {
            _logger.LogWarning("Artifact {ArtifactId} created ACK is missing upload_url or upload_session_id.", artifactId);
            return;
        }

        var method = TryReadString(result, "method") ?? TryReadString(result, "upload_method") ?? "PUT";
        var headersJson = TryReadHeadersJson(result);
        var expiresAt = TryReadDateTime(result, "expires_at");

        await _artifacts.SetUploadInstructionsAsync(
            artifact.ArtifactId,
            uploadSessionId,
            uploadUrl,
            method,
            headersJson,
            expiresAt,
            nowUtc,
            ct);

        _logger.LogInformation("Artifact {ArtifactId} received upload instructions from Portal.", artifact.ArtifactId);
    }

    private async Task HandleUploadedAckAsync(
        OutboxMessage originalMessage,
        MessageAcknowledgementPayload acknowledgement,
        DateTime nowUtc,
        CancellationToken ct)
    {
        var artifactId = TryReadString(originalMessage.PayloadJson, "artifact_id");
        if (string.IsNullOrWhiteSpace(artifactId))
            return;

        var artifact = await _artifacts.GetAsync(artifactId, ct);
        if (artifact is null)
            return;

        if (artifact.Status == ArtifactStatus.Confirmed)
            return;

        var result = acknowledgement.Result;
        if (result.ValueKind is JsonValueKind.Undefined or JsonValueKind.Null)
        {
            _logger.LogWarning("Artifact {ArtifactId} uploaded ACK did not include confirmation details.", artifactId);
            return;
        }

        var status = TryReadString(result, "status");
        if (!string.Equals(status, "available", StringComparison.OrdinalIgnoreCase) &&
            !string.Equals(status, "confirmed", StringComparison.OrdinalIgnoreCase))
        {
            _logger.LogWarning("Artifact {ArtifactId} uploaded ACK returned non-final status {Status}.", artifactId, status);
            return;
        }

        var remoteObjectId = TryReadString(result, "stored_object_id") ?? artifact.RemoteObjectId;
        await _artifacts.UpdateStatusAsync(
            artifact.ArtifactId,
            ArtifactStatus.Confirmed,
            availableAtUtc: null,
            uploadedAtUtc: artifact.UploadedAtUtc ?? nowUtc,
            confirmedAtUtc: nowUtc,
            remoteObjectId: remoteObjectId,
            attemptCount: artifact.AttemptCount,
            lastError: null,
            ct);

        TryCleanupConfirmedLocalFile(artifact);
        _logger.LogInformation("Artifact {ArtifactId} confirmed by Portal ACK.", artifact.ArtifactId);
    }

    private static string? TryReadString(string json, string propertyName)
    {
        try
        {
            using var document = JsonDocument.Parse(json);
            return TryReadString(document.RootElement, propertyName);
        }
        catch (JsonException)
        {
            return null;
        }
    }

    private static string? TryReadString(JsonElement element, string propertyName)
    {
        return element.TryGetProperty(propertyName, out var value) && value.ValueKind == JsonValueKind.String
            ? value.GetString()
            : null;
    }

    private static DateTime? TryReadDateTime(JsonElement element, string propertyName)
    {
        var raw = TryReadString(element, propertyName);
        if (!DateTime.TryParse(raw, CultureInfo.InvariantCulture, DateTimeStyles.RoundtripKind, out var parsed))
            return null;

        return parsed.Kind switch
        {
            DateTimeKind.Utc => parsed,
            DateTimeKind.Local => parsed.ToUniversalTime(),
            _ => DateTime.SpecifyKind(parsed, DateTimeKind.Utc)
        };
    }

    private static string? TryReadHeadersJson(JsonElement result)
    {
        if (!result.TryGetProperty("headers", out var headers) || headers.ValueKind != JsonValueKind.Object)
            return null;

        var values = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (var header in headers.EnumerateObject())
        {
            var value = header.Value.ValueKind == JsonValueKind.String
                ? header.Value.GetString()
                : header.Value.ToString();
            if (!string.IsNullOrWhiteSpace(header.Name) && value is not null)
                values[header.Name] = value;
        }

        return values.Count == 0 ? null : JsonSerializer.Serialize(values);
    }

    private void TryCleanupConfirmedLocalFile(PendingArtifactRecord artifact)
    {
        if (_options.ArtifactKeepConfirmedLocalHours > 0)
            return;

        try
        {
            if (File.Exists(artifact.LocalPath))
                File.Delete(artifact.LocalPath);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to cleanup confirmed artifact file {Path}.", artifact.LocalPath);
        }
    }
}
