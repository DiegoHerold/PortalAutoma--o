using Biason.AutomationAgent.Application.Execution;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models;
using Biason.AutomationAgent.Domain.Models.Execution;
using Biason.AutomationAgent.Domain.Models.Messaging;
using Biason.AutomationAgent.Domain.Models.Storage;
using Biason.AutomationAgent.Protocol.Messages;
using Biason.AutomationAgent.Protocol.Serialization;
using Microsoft.Extensions.Logging;

namespace Biason.AutomationAgent.Application.Messaging.Handlers;

/// <summary>
/// Processa <c>execution.offer</c> vindo do Portal (Bloco 5.5, seção 5-7).
/// Fluxo: Inbox -&gt; valida payload -&gt; idempotência por execution_attempt_id
/// -&gt; garante pacote/manifesto disponíveis -&gt; Admission Controller (que já
/// cria a reserva TEMPORARY quando aceita) -&gt; execution.accept/reject via
/// Outbox. Não reimplementa admissão nem reservas — apenas coordena os
/// componentes existentes.
/// </summary>
public sealed class ExecutionOfferHandler : IInboxCommandHandler
{
    private static readonly HashSet<string> NonRetryableRejectionCodes = new(StringComparer.Ordinal)
    {
        "INTERACTIVE_CAPABILITY_NOT_AVAILABLE",
        "MANIFEST_INVALID",
        "MANIFEST_NOT_FOUND",
        "EXECUTION_ATTEMPT_CONFLICT",
        "PACKAGE_HASH_MISMATCH",
        "INVALID_OFFER_PAYLOAD"
    };

    private readonly IExecutionOfferRepository _offers;
    private readonly IExecutionRepository _execRepo;
    private readonly IPackageStore _packageStore;
    private readonly IManifestValidator _manifestValidator;
    private readonly IAdmissionController _admission;
    private readonly IResourceReservationManager _reservations;
    private readonly IAgentIdentityService _identity;
    private readonly OutboxMessagePublisher _outboxPublisher;
    private readonly IDownloadManager _downloadManager;
    private readonly IDirectoryResolver _dirs;
    private readonly IClock _clock;
    private readonly ILogger<ExecutionOfferHandler> _logger;

    public ExecutionOfferHandler(
        IExecutionOfferRepository offers,
        IExecutionRepository execRepo,
        IPackageStore packageStore,
        IManifestValidator manifestValidator,
        IAdmissionController admission,
        IResourceReservationManager reservations,
        IAgentIdentityService identity,
        OutboxMessagePublisher outboxPublisher,
        IDownloadManager downloadManager,
        IDirectoryResolver dirs,
        IClock clock,
        ILogger<ExecutionOfferHandler> logger)
    {
        _offers = offers;
        _execRepo = execRepo;
        _packageStore = packageStore;
        _manifestValidator = manifestValidator;
        _admission = admission;
        _reservations = reservations;
        _identity = identity;
        _outboxPublisher = outboxPublisher;
        _downloadManager = downloadManager;
        _dirs = dirs;
        _clock = clock;
        _logger = logger;
    }

    public string MessageType => PortalMessageTypes.ExecutionOffer;

    public async Task<InboxCommandHandlerResult> HandleAsync(InboxCommand command, CancellationToken ct = default)
    {
        var payload = ProtocolJson.Deserialize<ExecutionOfferPayload>(command.PayloadJson);
        if (payload is null || string.IsNullOrEmpty(payload.ExecutionAttemptId) || payload.Package is null || payload.Runtime is null)
        {
            _logger.LogWarning("execution.offer with invalid payload (message {MessageId})", command.MessageId);
            return InboxCommandHandlerResult.Dead("INVALID_OFFER_PAYLOAD");
        }

        var attemptId = command.ExecutionAttemptId ?? payload.ExecutionAttemptId;
        var executionId = command.ExecutionId ?? payload.ExecutionId ?? payload.TaskExecutionId;
        if (string.IsNullOrEmpty(attemptId) || string.IsNullOrEmpty(executionId))
        {
            _logger.LogWarning("execution.offer without execution_id/execution_attempt_id (message {MessageId})", command.MessageId);
            return InboxCommandHandlerResult.Dead("INVALID_OFFER_ENVELOPE");
        }

        // === Idempotência por tentativa (seção 6) ===
        var previousOffer = await _offers.GetLatestByAttemptAsync(attemptId, ct);
        if (previousOffer is not null)
        {
            if (string.Equals(previousOffer.OfferPayloadJson, command.PayloadJson, StringComparison.Ordinal))
            {
                _logger.LogInformation("Duplicate identical execution.offer for attempt {AttemptId}; resending prior decision.", attemptId);
                await ResendDecisionAsync(previousOffer, ct);
                return InboxCommandHandlerResult.Processed("duplicate_offer_resent");
            }

            _logger.LogWarning("execution.offer for attempt {AttemptId} conflicts with a previously recorded offer.", attemptId);
            await RejectAsync(command, payload, executionId, attemptId, "EXECUTION_ATTEMPT_CONFLICT",
                "A different offer was already recorded for this execution attempt.", ct);
            return InboxCommandHandlerResult.Processed("offer_conflict_rejected");
        }

        // === Pacote e manifesto ===
        var packageId = payload.Package.Id;
        if (!_packageStore.Exists(packageId))
        {
            var provisioned = await TryProvisionPackageAsync(payload, ct);
            if (!provisioned)
            {
                await RejectAsync(command, payload, executionId, attemptId, "PACKAGE_NOT_AVAILABLE",
                    $"Package {packageId} is not available locally and could not be provisioned.", ct);
                return InboxCommandHandlerResult.Processed("rejected");
            }
        }

        var artifact = await _packageStore.GetArtifactAsync(packageId, ct);
        if (artifact is null || !File.Exists(artifact.ManifestPath))
        {
            await RejectAsync(command, payload, executionId, attemptId, "MANIFEST_NOT_FOUND",
                $"Manifest for package {packageId} was not found.", ct);
            return InboxCommandHandlerResult.Processed("rejected");
        }

        var validation = await _manifestValidator.ValidateAsync(artifact.ManifestPath, ct);
        if (!validation.IsValid || validation.Manifest is null)
        {
            await RejectAsync(command, payload, executionId, attemptId, "MANIFEST_INVALID",
                string.Join("; ", validation.Errors), ct);
            return InboxCommandHandlerResult.Processed("rejected");
        }

        var manifest = validation.Manifest;
        var inputJson = payload.Input.ValueKind is System.Text.Json.JsonValueKind.Undefined or System.Text.Json.JsonValueKind.Null
            ? null
            : payload.Input.GetRawText();

        var execution = new ExecutionRecord
        {
            ExecutionId = executionId,
            CurrentState = ExecutionState.Offered,
            CreatedAtUtc = _clock.UtcNow,
            LastTransitionUtc = _clock.UtcNow,
            // O contrato de execution.offer não distingue automation_id de
            // automation_version_id; usamos o mesmo valor para ambos.
            // AutomationVersionId carrega o package_id real (o identificador
            // que o PackageStore/ExecutionManager efetivamente usam para
            // resolver o pacote em disco).
            AutomationId = payload.AutomationVersionId,
            AutomationVersionId = packageId,
            Pool = manifest.Resources?.Pool ?? PoolType.Background,
            CurrentAttemptId = attemptId,
            InputJson = inputJson
        };
        await _execRepo.SaveAsync(execution, ct);

        var decision = await _admission.EvaluateAsync(execution, manifest, ct);

        if (!decision.Accepted)
        {
            await ExecutionTransitions.TransitionAsync(_execRepo, _clock, execution, ExecutionState.Rejected, ct);
            await PersistOfferAsync(command, payload, executionId, attemptId, manifest, OfferDecision.Rejected,
                decision.RejectionCode, decision.RejectionReason, reservationId: null, reservationExpiresAtUtc: null, ct);
            await SendRejectAsync(payload, executionId, attemptId, decision.RejectionCode ?? "ADMISSION_REJECTED", decision.RejectionReason, ct);
            return InboxCommandHandlerResult.Processed("rejected");
        }

        execution.ReservationId = decision.ReservationId;
        await ExecutionTransitions.TransitionAsync(_execRepo, _clock, execution, ExecutionState.Reserved, ct);

        var reservation = decision.ReservationId is not null ? await _reservations.GetAsync(decision.ReservationId, ct) : null;

        await PersistOfferAsync(command, payload, executionId, attemptId, manifest, OfferDecision.Accepted,
            reasonCode: null, reasonMessage: null, reservationId: decision.ReservationId, reservationExpiresAtUtc: reservation?.ExpiresAtUtc, ct);

        var localIdentity = await _identity.GetIdentityAsync(ct);
        var acceptedPool = (manifest.Resources?.Pool ?? PoolType.Background).ToString().ToLowerInvariant();

        await _outboxPublisher.EnqueueAsync(
            PortalMessageTypes.ExecutionAccept,
            new ExecutionAcceptPayload
            {
                ExecutionOfferId = payload.ExecutionOfferId,
                ExecutionAttemptId = attemptId,
                AgentId = localIdentity?.AgentId ?? string.Empty,
                AgentInstanceId = localIdentity?.InstanceId ?? string.Empty,
                AcceptedAt = _clock.UtcNow,
                ReservedPools = new Dictionary<string, int>(StringComparer.Ordinal)
                {
                    [acceptedPool] = 1
                },
                ResourceReservations = decision.ReservationId is null
                    ? Array.Empty<string>()
                    : new[] { decision.ReservationId }
            },
            executionId: executionId,
            executionAttemptId: attemptId,
            ct: ct);

        _logger.LogInformation("execution.offer accepted: execution={ExecutionId}, attempt={AttemptId}, reservation={ReservationId}",
            executionId, attemptId, decision.ReservationId);

        return InboxCommandHandlerResult.Processed("accepted");
    }

    private async Task<bool> TryProvisionPackageAsync(ExecutionOfferPayload payload, CancellationToken ct)
    {
        if (string.IsNullOrEmpty(payload.Package.DownloadUrl))
            return false;

        try
        {
            var targetPath = Path.Combine(_dirs.DownloadsPath, $"{payload.Package.Id}.zip");
            var download = await _downloadManager.DownloadAsync(new DownloadRequest
            {
                DownloadId = $"pkg_{payload.Package.Id}",
                Url = payload.Package.DownloadUrl,
                TargetPath = targetPath,
                ExpectedSha256 = payload.Package.Sha256,
                ExpectedSizeBytes = payload.Package.SizeBytes,
                CreatedAtUtc = _clock.UtcNow
            }, ct);

            if (!download.Success || download.FilePath is null)
            {
                _logger.LogWarning("Failed to download package {PackageId}: {Error}", payload.Package.Id, download.ErrorMessage);
                return false;
            }

            await _packageStore.ImportAsync(
                payload.Package.Id,
                payload.AutomationVersionId,
                payload.AutomationVersionId,
                payload.AutomationVersionId,
                download.FilePath,
                payload.Package.Sha256,
                ct);

            return true;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error provisioning package {PackageId} on-demand.", payload.Package.Id);
            return false;
        }
    }

    private async Task PersistOfferAsync(
        InboxCommand command,
        ExecutionOfferPayload payload,
        string executionId,
        string attemptId,
        AutomationManifest? manifest,
        string decision,
        string? reasonCode,
        string? reasonMessage,
        string? reservationId,
        DateTime? reservationExpiresAtUtc,
        CancellationToken ct)
    {
        await _offers.SaveAsync(new ExecutionOfferRecord
        {
            OfferMessageId = command.MessageId,
            ExecutionId = executionId,
            ExecutionAttemptId = attemptId,
            AutomationId = payload.AutomationVersionId,
            AutomationVersion = payload.AutomationVersionId,
            RuntimeId = payload.Runtime.Id,
            RuntimeVersion = payload.Runtime.Version,
            Mode = manifest?.Execution?.Mode ?? "background",
            Pool = (manifest?.Resources?.Pool ?? PoolType.Background).ToString().ToLowerInvariant(),
            OfferPayloadJson = command.PayloadJson,
            Decision = decision,
            ReasonCode = reasonCode,
            ReasonMessage = reasonMessage,
            ReservationId = reservationId,
            ReceivedAtUtc = command.ReceivedAtUtc,
            DecidedAtUtc = _clock.UtcNow,
            ReservationExpiresAtUtc = reservationExpiresAtUtc
        }, ct);
    }

    private async Task RejectAsync(
        InboxCommand command,
        ExecutionOfferPayload payload,
        string executionId,
        string attemptId,
        string reasonCode,
        string? reasonMessage,
        CancellationToken ct)
    {
        await PersistOfferAsync(command, payload, executionId, attemptId, manifest: null, OfferDecision.Rejected,
            reasonCode, reasonMessage, reservationId: null, reservationExpiresAtUtc: null, ct);
        await SendRejectAsync(payload, executionId, attemptId, reasonCode, reasonMessage, ct);
    }

    private async Task SendRejectAsync(ExecutionOfferPayload payload, string executionId, string attemptId, string reasonCode, string? details, CancellationToken ct)
    {
        var localIdentity = await _identity.GetIdentityAsync(ct);
        var portalReasonCode = ToPortalRejectionCode(reasonCode);
        await _outboxPublisher.EnqueueAsync(
            PortalMessageTypes.ExecutionReject,
            new ExecutionRejectPayload
            {
                ExecutionOfferId = payload.ExecutionOfferId,
                ExecutionAttemptId = attemptId,
                TaskExecutionId = payload.TaskExecutionId,
                AgentId = localIdentity?.AgentId ?? string.Empty,
                AgentInstanceId = localIdentity?.InstanceId ?? string.Empty,
                RejectionCode = portalReasonCode,
                RejectionDetails = new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["agent_reason_code"] = reasonCode,
                    ["message"] = details,
                    ["retryable"] = !NonRetryableRejectionCodes.Contains(reasonCode)
                },
                RejectedAt = _clock.UtcNow
            },
            executionId: executionId,
            executionAttemptId: attemptId,
            ct: ct);
    }

    private async Task ResendDecisionAsync(ExecutionOfferRecord previousOffer, CancellationToken ct)
    {
        var originalPayload = ProtocolJson.Deserialize<ExecutionOfferPayload>(previousOffer.OfferPayloadJson);
        var executionOfferId = originalPayload?.ExecutionOfferId ?? previousOffer.OfferMessageId;
        var localIdentity = await _identity.GetIdentityAsync(ct);

        if (previousOffer.Decision == OfferDecision.Accepted && previousOffer.ReservationId is not null)
        {
            await _outboxPublisher.EnqueueAsync(
                PortalMessageTypes.ExecutionAccept,
                new ExecutionAcceptPayload
                {
                    ExecutionOfferId = executionOfferId,
                    ExecutionAttemptId = previousOffer.ExecutionAttemptId,
                    AgentId = localIdentity?.AgentId ?? string.Empty,
                    AgentInstanceId = localIdentity?.InstanceId ?? string.Empty,
                    AcceptedAt = _clock.UtcNow,
                    ReservedPools = new Dictionary<string, int>(StringComparer.Ordinal)
                    {
                        [previousOffer.Pool] = 1
                    },
                    ResourceReservations = new[] { previousOffer.ReservationId }
                },
                executionId: previousOffer.ExecutionId,
                executionAttemptId: previousOffer.ExecutionAttemptId,
                ct: ct);
        }
        else
        {
            await _outboxPublisher.EnqueueAsync(
                PortalMessageTypes.ExecutionReject,
                new ExecutionRejectPayload
                {
                    ExecutionOfferId = executionOfferId,
                    ExecutionAttemptId = previousOffer.ExecutionAttemptId,
                    TaskExecutionId = originalPayload?.TaskExecutionId,
                    AgentId = localIdentity?.AgentId ?? string.Empty,
                    AgentInstanceId = localIdentity?.InstanceId ?? string.Empty,
                    RejectionCode = ToPortalRejectionCode(previousOffer.ReasonCode ?? "ADMISSION_REJECTED"),
                    RejectionDetails = new Dictionary<string, object?>(StringComparer.Ordinal)
                    {
                        ["agent_reason_code"] = previousOffer.ReasonCode,
                        ["message"] = previousOffer.ReasonMessage,
                        ["retryable"] = !NonRetryableRejectionCodes.Contains(previousOffer.ReasonCode ?? string.Empty)
                    },
                    RejectedAt = _clock.UtcNow
                },
                executionId: previousOffer.ExecutionId,
                executionAttemptId: previousOffer.ExecutionAttemptId,
                ct: ct);
        }
    }

    private static string ToPortalRejectionCode(string? reasonCode) =>
        reasonCode switch
        {
            "INSUFFICIENT_MEMORY" => "INSUFFICIENT_MEMORY",
            "INSUFFICIENT_DISK" => "INSUFFICIENT_DISK",
            "INSUFFICIENT_CPU_CAPACITY" => "INSUFFICIENT_CPU_CAPACITY",
            "INTERACTIVE_SESSION_LOCKED" => "INTERACTIVE_SESSION_LOCKED",
            "INTERACTIVE_SESSION_UNAVAILABLE" or
            "INTERACTIVE_SESSION_NOT_AVAILABLE" or
            "INTERACTIVE_SESSION_DISCONNECTED" or
            "NO_ACTIVE_UNLOCKED_SESSION" => "INTERACTIVE_SESSION_UNAVAILABLE",
            "INTERACTIVE_POOL_FULL" => "AGENT_OVERLOADED",
            "INTERACTIVE_CAPABILITY_NOT_AVAILABLE" or
            "CAPABILITY_NOT_AVAILABLE" or
            "CAPABILITY_UNAVAILABLE" => "CAPABILITY_UNAVAILABLE",
            "DESKTOP_RESOURCE_BUSY" or
            "EXCLUSIVE_RESOURCE_BUSY" or
            "RESOURCE_LOCKED" => "RESOURCE_LOCKED",
            "AGENT_DRAINING" => "AGENT_DRAINING",
            "AGENT_DISABLED" => "AGENT_DISABLED",
            "AGENT_OVERLOADED" => "AGENT_OVERLOADED",
            "RUNTIME_UNAVAILABLE" => "RUNTIME_UNAVAILABLE",
            "PACKAGE_UNAVAILABLE" or
            "PACKAGE_NOT_AVAILABLE" or
            "PACKAGE_HASH_MISMATCH" or
            "MANIFEST_NOT_FOUND" or
            "MANIFEST_INVALID" => "PACKAGE_UNAVAILABLE",
            "RUNTIME_PREPARATION_FAILED" => "RUNTIME_PREPARATION_FAILED",
            "PACKAGE_PREPARATION_FAILED" => "PACKAGE_PREPARATION_FAILED",
            "PROTOCOL_INCOMPATIBLE" or
            "INVALID_OFFER_PAYLOAD" or
            "EXECUTION_ATTEMPT_CONFLICT" => "PROTOCOL_INCOMPATIBLE",
            _ => "AGENT_OVERLOADED"
        };
}
