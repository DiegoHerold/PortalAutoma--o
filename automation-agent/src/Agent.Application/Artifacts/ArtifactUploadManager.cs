using System.Security.Cryptography;
using System.Text.Json;
using Biason.AutomationAgent.Application.Messaging;
using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Execution;
using Biason.AutomationAgent.Protocol.Envelope;
using Biason.AutomationAgent.Protocol.Messages;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace Biason.AutomationAgent.Application.Artifacts;

public sealed class ArtifactUploadManager : IArtifactUploadManager
{
    private readonly IPendingArtifactRepository _artifacts;
    private readonly IArtifactContentUploader _uploader;
    private readonly OutboxMessagePublisher _outboxPublisher;
    private readonly IClock _clock;
    private readonly ExecutionOptions _options;
    private readonly ILogger<ArtifactUploadManager> _logger;

    public ArtifactUploadManager(
        IPendingArtifactRepository artifacts,
        IArtifactContentUploader uploader,
        OutboxMessagePublisher outboxPublisher,
        IClock clock,
        IOptions<ExecutionOptions> options,
        ILogger<ArtifactUploadManager> logger)
    {
        _artifacts = artifacts;
        _uploader = uploader;
        _outboxPublisher = outboxPublisher;
        _clock = clock;
        _options = options.Value;
        _logger = logger;
    }

    public async Task RecoverUploadingAsync(CancellationToken ct = default)
    {
        var nonFinal = await _artifacts.GetNonFinalAsync(500, ct);
        foreach (var artifact in nonFinal)
        {
            if (artifact.Status == ArtifactStatus.Uploading)
            {
                await MarkRetryAsync(artifact, "ARTIFACT_UPLOAD_INTERRUPTED", ct);
                continue;
            }

            if (artifact.Status == ArtifactStatus.Pending && string.IsNullOrWhiteSpace(artifact.AnnouncementMessageId))
            {
                await EnqueueCreatedEventAsync(artifact, ct);
                continue;
            }

            if (artifact.Status == ArtifactStatus.Uploaded && !string.IsNullOrWhiteSpace(artifact.UploadSessionId))
                await EnqueueUploadedEventAsync(artifact, artifact.UploadedAtUtc ?? _clock.UtcNow, ct);
        }
    }

    public async Task<int> ProcessDueAsync(CancellationToken ct = default)
    {
        var now = _clock.UtcNow;
        var candidates = await _artifacts.GetUploadCandidatesAsync(now, _options.ArtifactUploadBatchSize, ct);
        var processed = 0;

        foreach (var artifact in candidates)
        {
            ct.ThrowIfCancellationRequested();
            await ProcessOneAsync(artifact, ct);
            processed++;
        }

        return processed;
    }

    private async Task ProcessOneAsync(PendingArtifactRecord artifact, CancellationToken ct)
    {
        if (string.IsNullOrWhiteSpace(artifact.UploadUrl) || string.IsNullOrWhiteSpace(artifact.UploadSessionId))
        {
            await MarkRetryAsync(artifact, "ARTIFACT_UPLOAD_INSTRUCTIONS_MISSING", ct);
            return;
        }

        if (!IsSafeArtifactPathShape(artifact))
        {
            await MarkFailedAndPublishAsync(artifact, "ARTIFACT_LOCAL_PATH_UNAUTHORIZED", ct);
            return;
        }

        if (artifact.UploadExpiresAtUtc is not null && artifact.UploadExpiresAtUtc <= _clock.UtcNow)
        {
            await EnqueueCreatedEventAsync(artifact, forceNewMessageId: true, ct);
            _logger.LogWarning("Artifact {ArtifactId} upload URL expired; re-announced artifact for fresh instructions.", artifact.ArtifactId);
            return;
        }

        if (!File.Exists(artifact.LocalPath))
        {
            await MarkFailedAndPublishAsync(artifact, "ARTIFACT_LOCAL_FILE_MISSING", ct);
            return;
        }

        if (File.GetAttributes(artifact.LocalPath).HasFlag(FileAttributes.ReparsePoint))
        {
            await MarkFailedAndPublishAsync(artifact, "ARTIFACT_LOCAL_PATH_UNAUTHORIZED", ct);
            return;
        }

        var actual = await HashLocalFileAsync(artifact.LocalPath, ct);
        if (actual.SizeBytes > (long)_options.ArtifactMaxSizeMb * 1024 * 1024)
        {
            await MarkFailedAndPublishAsync(artifact, "ARTIFACT_TOO_LARGE", ct);
            return;
        }

        if (artifact.SizeBytes != actual.SizeBytes)
        {
            await MarkFailedAndPublishAsync(artifact, "ARTIFACT_LOCAL_FILE_SIZE_MISMATCH", ct);
            return;
        }

        if (!string.Equals(artifact.Sha256, actual.Sha256, StringComparison.OrdinalIgnoreCase))
        {
            await MarkFailedAndPublishAsync(artifact, "ARTIFACT_LOCAL_FILE_HASH_MISMATCH", ct);
            return;
        }

        artifact.AttemptCount++;
        await _artifacts.UpdateStatusAsync(
            artifact.ArtifactId,
            ArtifactStatus.Uploading,
            availableAtUtc: null,
            uploadedAtUtc: artifact.UploadedAtUtc,
            confirmedAtUtc: artifact.ConfirmedAtUtc,
            remoteObjectId: artifact.RemoteObjectId,
            attemptCount: artifact.AttemptCount,
            lastError: null,
            ct);

        var upload = await _uploader.UploadAsync(BuildUploadTarget(artifact), artifact.LocalPath, artifact.ContentType, ct);
        if (!upload.Success)
        {
            await MarkFailedOrRetryAsync(artifact, upload.ReasonCode ?? "ARTIFACT_UPLOAD_FAILED", upload.Retryable, ct);
            return;
        }

        await EnqueueUploadedEventAsync(artifact, _clock.UtcNow, ct);
        _logger.LogInformation("Artifact {ArtifactId} bytes uploaded; awaiting Portal confirmation ACK.", artifact.ArtifactId);
    }

    private async Task EnqueueCreatedEventAsync(PendingArtifactRecord artifact, CancellationToken ct) =>
        await EnqueueCreatedEventAsync(artifact, forceNewMessageId: false, ct);

    private async Task EnqueueCreatedEventAsync(PendingArtifactRecord artifact, bool forceNewMessageId, CancellationToken ct)
    {
        var messageId = forceNewMessageId ? ProtocolEnvelope.NewMessageId() : artifact.AnnouncementMessageId ?? ProtocolEnvelope.NewMessageId();
        await _artifacts.SetAnnouncementAsync(artifact.ArtifactId, messageId, ArtifactStatus.Announced, ct);
        await _outboxPublisher.EnqueueAsync(
            PortalMessageTypes.ExecutionArtifactCreated,
            new ExecutionArtifactCreatedPayload
            {
                ArtifactId = artifact.ArtifactId,
                ExecutionId = artifact.ExecutionId,
                ExecutionAttemptId = artifact.ExecutionAttemptId,
                Name = artifact.Name,
                ContentType = artifact.ContentType,
                SizeBytes = artifact.SizeBytes,
                Sha256 = artifact.Sha256,
                Status = ArtifactStatus.Announced.ToString().ToUpperInvariant()
            },
            executionId: artifact.ExecutionId,
            executionAttemptId: artifact.ExecutionAttemptId,
            messageId: messageId,
            ct: ct);
    }

    private async Task EnqueueUploadedEventAsync(PendingArtifactRecord artifact, DateTime uploadedAtUtc, CancellationToken ct)
    {
        var messageId = artifact.UploadedMessageId ?? ProtocolEnvelope.NewMessageId();
        await _artifacts.SetUploadedMessageAsync(
            artifact.ArtifactId,
            messageId,
            ArtifactStatus.Uploaded,
            uploadedAtUtc,
            remoteObjectId: artifact.UploadSessionId,
            lastError: null,
            ct);

        await _outboxPublisher.EnqueueAsync(
            PortalMessageTypes.ArtifactUploaded,
            new ArtifactUploadedPayload
            {
                ArtifactId = artifact.ArtifactId,
                ExecutionId = artifact.ExecutionId,
                ExecutionAttemptId = artifact.ExecutionAttemptId,
                UploadSessionId = artifact.UploadSessionId!,
                SizeBytes = artifact.SizeBytes,
                Sha256 = artifact.Sha256
            },
            executionId: artifact.ExecutionId,
            executionAttemptId: artifact.ExecutionAttemptId,
            messageId: messageId,
            ct: ct);
    }

    private async Task MarkFailedOrRetryAsync(PendingArtifactRecord artifact, string reasonCode, bool retryable, CancellationToken ct)
    {
        if (!retryable || artifact.AttemptCount >= _options.ArtifactUploadMaxAttempts)
        {
            await MarkFailedAndPublishAsync(artifact, reasonCode, ct);
            return;
        }

        await MarkRetryAsync(artifact, reasonCode, ct);
    }

    private async Task MarkRetryAsync(PendingArtifactRecord artifact, string reasonCode, CancellationToken ct)
    {
        var delaySeconds = _options.ArtifactRetryBaseDelaySeconds * Math.Max(1, artifact.AttemptCount);
        await _artifacts.UpdateStatusAsync(
            artifact.ArtifactId,
            ArtifactStatus.RetryWait,
            availableAtUtc: _clock.UtcNow.AddSeconds(delaySeconds),
            uploadedAtUtc: artifact.UploadedAtUtc,
            confirmedAtUtc: artifact.ConfirmedAtUtc,
            remoteObjectId: artifact.RemoteObjectId,
            attemptCount: artifact.AttemptCount,
            lastError: reasonCode,
            ct);

        _logger.LogWarning(
            "Artifact {ArtifactId} upload will retry in {DelaySeconds}s ({ReasonCode}).",
            artifact.ArtifactId, delaySeconds, reasonCode);
    }

    private async Task MarkFailedAndPublishAsync(PendingArtifactRecord artifact, string reasonCode, CancellationToken ct)
    {
        var messageId = artifact.FailedMessageId ?? ProtocolEnvelope.NewMessageId();
        await _artifacts.SetFailedMessageAsync(artifact.ArtifactId, messageId, ct);
        await _outboxPublisher.EnqueueAsync(
            PortalMessageTypes.ArtifactFailed,
            new ArtifactFailedPayload
            {
                ArtifactId = artifact.ArtifactId,
                ExecutionId = artifact.ExecutionId,
                ExecutionAttemptId = artifact.ExecutionAttemptId,
                UploadSessionId = artifact.UploadSessionId,
                Reason = reasonCode
            },
            executionId: artifact.ExecutionId,
            executionAttemptId: artifact.ExecutionAttemptId,
            messageId: messageId,
            ct: ct);

        await _artifacts.UpdateStatusAsync(
            artifact.ArtifactId,
            ArtifactStatus.Failed,
            availableAtUtc: null,
            uploadedAtUtc: artifact.UploadedAtUtc,
            confirmedAtUtc: artifact.ConfirmedAtUtc,
            remoteObjectId: artifact.RemoteObjectId,
            attemptCount: artifact.AttemptCount,
            lastError: reasonCode,
            ct);

        _logger.LogWarning("Artifact {ArtifactId} failed permanently ({ReasonCode}).", artifact.ArtifactId, reasonCode);
    }

    private static PortalArtifactUploadTarget BuildUploadTarget(PendingArtifactRecord artifact)
    {
        return new PortalArtifactUploadTarget(
            artifact.UploadUrl!,
            string.IsNullOrWhiteSpace(artifact.UploadMethod) ? "PUT" : artifact.UploadMethod,
            artifact.UploadSessionId,
            ReadHeaders(artifact.UploadHeadersJson));
    }

    private static IReadOnlyDictionary<string, string>? ReadHeaders(string? headersJson)
    {
        if (string.IsNullOrWhiteSpace(headersJson))
            return null;

        try
        {
            return JsonSerializer.Deserialize<Dictionary<string, string>>(headersJson);
        }
        catch (JsonException)
        {
            return null;
        }
    }

    private static async Task<(string Sha256, long SizeBytes)> HashLocalFileAsync(string path, CancellationToken ct)
    {
        await using var stream = File.OpenRead(path);
        using var sha = SHA256.Create();
        var hash = await sha.ComputeHashAsync(stream, ct);
        return (Convert.ToHexString(hash).ToLowerInvariant(), stream.Length);
    }

    private static bool IsSafeArtifactPathShape(PendingArtifactRecord artifact)
    {
        if (string.IsNullOrWhiteSpace(artifact.LocalPath) ||
            string.IsNullOrWhiteSpace(artifact.Name) ||
            Path.IsPathRooted(artifact.Name))
            return false;

        var segments = artifact.Name.Split(new[] { '/', '\\' }, StringSplitOptions.RemoveEmptyEntries);
        if (segments.Length == 0 || segments.Any(s => s == "." || s == ".."))
            return false;

        string fullPath;
        try
        {
            fullPath = Path.GetFullPath(artifact.LocalPath);
        }
        catch
        {
            return false;
        }

        var normalizedName = Path.Combine(segments);
        if (!fullPath.EndsWith(Path.DirectorySeparatorChar + normalizedName, StringComparison.OrdinalIgnoreCase))
            return false;

        var artifactRoot = fullPath[..^normalizedName.Length].TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        if (!string.Equals(Path.GetFileName(artifactRoot), "artifacts", StringComparison.OrdinalIgnoreCase))
            return false;

        var expectedPath = Path.GetFullPath(Path.Combine(artifactRoot, normalizedName));
        return string.Equals(fullPath, expectedPath, StringComparison.OrdinalIgnoreCase);
    }
}
