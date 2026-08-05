using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Execution;
using Biason.AutomationAgent.Domain.Models.Messaging;
using Biason.AutomationAgent.Protocol.Messages;
using Biason.AutomationAgent.Protocol.Serialization;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace Biason.AutomationAgent.Application.Messaging.Handlers;

public sealed class ArtifactConfirmedHandler : IInboxCommandHandler
{
    private readonly IPendingArtifactRepository _artifacts;
    private readonly IClock _clock;
    private readonly ExecutionOptions _options;
    private readonly ILogger<ArtifactConfirmedHandler> _logger;

    public ArtifactConfirmedHandler(
        IPendingArtifactRepository artifacts,
        IClock clock,
        ILogger<ArtifactConfirmedHandler> logger,
        IOptions<ExecutionOptions>? options = null)
    {
        _artifacts = artifacts;
        _clock = clock;
        _options = options?.Value ?? new ExecutionOptions();
        _logger = logger;
    }

    public string MessageType => PortalMessageTypes.ArtifactConfirmed;

    public async Task<InboxCommandHandlerResult> HandleAsync(InboxCommand command, CancellationToken ct = default)
    {
        var payload = ProtocolJson.Deserialize<ArtifactConfirmedPayload>(command.PayloadJson);
        if (payload is null || string.IsNullOrEmpty(payload.ArtifactId))
            return InboxCommandHandlerResult.Dead("INVALID_ARTIFACT_CONFIRMATION_PAYLOAD");

        var artifact = await _artifacts.GetAsync(payload.ArtifactId, ct);
        if (artifact is null)
            return InboxCommandHandlerResult.Dead("ARTIFACT_NOT_FOUND");

        if (artifact.Status == ArtifactStatus.Confirmed)
            return InboxCommandHandlerResult.Processed("artifact_already_confirmed");

        await _artifacts.UpdateStatusAsync(
            artifact.ArtifactId,
            ArtifactStatus.Confirmed,
            availableAtUtc: null,
            uploadedAtUtc: artifact.UploadedAtUtc ?? _clock.UtcNow,
            confirmedAtUtc: _clock.UtcNow,
            remoteObjectId: payload.RemoteObjectId ?? artifact.RemoteObjectId,
            attemptCount: artifact.AttemptCount,
            lastError: null,
            ct);

        TryCleanupConfirmedLocalFile(artifact);
        _logger.LogInformation("Artifact {ArtifactId} confirmed by Portal.", artifact.ArtifactId);
        return InboxCommandHandlerResult.Processed("artifact_confirmed");
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
