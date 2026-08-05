using Biason.AutomationAgent.Application.Messaging;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Execution;
using Biason.AutomationAgent.Protocol.Envelope;
using Biason.AutomationAgent.Protocol.Messages;
using Microsoft.Extensions.Logging;

namespace Biason.AutomationAgent.Application.Artifacts;

public sealed class ArtifactManager : IArtifactManager
{
    private readonly IPendingArtifactRepository _artifacts;
    private readonly OutboxMessagePublisher _outboxPublisher;
    private readonly IClock _clock;
    private readonly ILogger<ArtifactManager> _logger;

    public ArtifactManager(
        IPendingArtifactRepository artifacts,
        OutboxMessagePublisher outboxPublisher,
        IClock clock,
        ILogger<ArtifactManager> logger)
    {
        _artifacts = artifacts;
        _outboxPublisher = outboxPublisher;
        _clock = clock;
        _logger = logger;
    }

    public async Task RegisterAsync(
        string executionId,
        string executionAttemptId,
        IReadOnlyList<ExecutionArtifactRef> artifacts,
        CancellationToken ct = default)
    {
        foreach (var artifact in artifacts)
        {
            var existing = await _artifacts.GetAsync(artifact.ArtifactId, ct);
            if (existing?.Status is ArtifactStatus.Confirmed or ArtifactStatus.Failed)
                continue;

            var announcementMessageId = existing?.AnnouncementMessageId ?? ProtocolEnvelope.NewMessageId();
            var record = new PendingArtifactRecord
            {
                ArtifactId = artifact.ArtifactId,
                ExecutionId = executionId,
                ExecutionAttemptId = executionAttemptId,
                Name = artifact.Name,
                ContentType = artifact.ContentType,
                SizeBytes = artifact.SizeBytes,
                Sha256 = artifact.Sha256,
                LocalPath = artifact.LocalPath,
                Status = ArtifactStatus.Announced,
                Kind = "execution_output",
                CreatedAtUtc = _clock.UtcNow,
                AvailableAtUtc = null,
                AnnouncementMessageId = announcementMessageId
            };

            await _artifacts.SaveAsync(record, ct);
            await _artifacts.SetAnnouncementAsync(record.ArtifactId, announcementMessageId, ArtifactStatus.Announced, ct);
            await _outboxPublisher.EnqueueAsync(
                PortalMessageTypes.ExecutionArtifactCreated,
                new ExecutionArtifactCreatedPayload
                {
                    ArtifactId = record.ArtifactId,
                    ExecutionId = executionId,
                    ExecutionAttemptId = executionAttemptId,
                    Name = record.Name,
                    ContentType = record.ContentType,
                    SizeBytes = record.SizeBytes,
                    Sha256 = record.Sha256,
                    Status = record.Status.ToString().ToUpperInvariant()
                },
                executionId: executionId,
                executionAttemptId: executionAttemptId,
                messageId: announcementMessageId,
                ct: ct);
        }

        if (artifacts.Count > 0)
        {
            _logger.LogInformation(
                "Registered {Count} pending artifact(s) for execution {ExecutionId}/{AttemptId}.",
                artifacts.Count, executionId, executionAttemptId);
        }
    }
}
