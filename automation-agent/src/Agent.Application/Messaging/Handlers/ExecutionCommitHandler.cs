using Biason.AutomationAgent.Application.Execution;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models;
using Biason.AutomationAgent.Domain.Models.Execution;
using Biason.AutomationAgent.Domain.Models.Messaging;
using Biason.AutomationAgent.Domain.StateMachines;
using Biason.AutomationAgent.Protocol.Messages;
using Biason.AutomationAgent.Protocol.Serialization;
using Microsoft.Extensions.Logging;

namespace Biason.AutomationAgent.Application.Messaging.Handlers;

/// <summary>
/// Processa <c>execution.commit</c> vindo do Portal (Bloco 5.5, seção 13-19).
/// Fluxo: Inbox -&gt; idempotência -&gt; commit atômico da reserva (compare-and-set
/// contra a expiração) -&gt; transição Reserved-&gt;Committed -&gt; dispara
/// ExecutionManager.ExecuteAsync (fire-and-forget: o método só retorna
/// quando a automação termina, então não pode ser aguardado dentro do ciclo
/// do InboxCommandProcessor). Não reimplementa o pipeline de execução —
/// apenas coordena o caso de uso e publica os eventos de protocolo em torno
/// dele, já que ExecutionManager não fala com o Outbox diretamente.
/// </summary>
public sealed class ExecutionCommitHandler : IInboxCommandHandler
{
    private readonly IExecutionCommitRepository _commits;
    private readonly IExecutionRepository _execRepo;
    private readonly IExecutionOfferRepository _offers;
    private readonly IExecutionLeaseRepository _leases;
    private readonly IResourceReservationManager _reservations;
    private readonly IPackageStore _packageStore;
    private readonly IManifestValidator _manifestValidator;
    private readonly IExecutionManager _executionManager;
    private readonly OutboxMessagePublisher _outboxPublisher;
    private readonly IArtifactManager? _artifactManager;
    private readonly IDesktopLockManager? _desktopLocks;
    private readonly IClock _clock;
    private readonly ILogger<ExecutionCommitHandler> _logger;

    public ExecutionCommitHandler(
        IExecutionCommitRepository commits,
        IExecutionRepository execRepo,
        IExecutionOfferRepository offers,
        IExecutionLeaseRepository leases,
        IResourceReservationManager reservations,
        IPackageStore packageStore,
        IManifestValidator manifestValidator,
        IExecutionManager executionManager,
        OutboxMessagePublisher outboxPublisher,
        IClock clock,
        ILogger<ExecutionCommitHandler> logger,
        IArtifactManager? artifactManager = null,
        IDesktopLockManager? desktopLocks = null)
    {
        _commits = commits;
        _execRepo = execRepo;
        _offers = offers;
        _leases = leases;
        _reservations = reservations;
        _packageStore = packageStore;
        _manifestValidator = manifestValidator;
        _executionManager = executionManager;
        _outboxPublisher = outboxPublisher;
        _artifactManager = artifactManager;
        _desktopLocks = desktopLocks;
        _clock = clock;
        _logger = logger;
    }

    public string MessageType => PortalMessageTypes.ExecutionCommit;

    public async Task<InboxCommandHandlerResult> HandleAsync(InboxCommand command, CancellationToken ct = default)
    {
        var payload = ProtocolJson.Deserialize<ExecutionCommitPayload>(command.PayloadJson);
        if (payload is null || string.IsNullOrEmpty(payload.ExecutionAttemptId))
        {
            _logger.LogWarning("execution.commit with invalid payload (message {MessageId})", command.MessageId);
            return InboxCommandHandlerResult.Dead("INVALID_COMMIT_PAYLOAD");
        }

        var attemptId = command.ExecutionAttemptId ?? payload.ExecutionAttemptId;
        var executionId = command.ExecutionId ?? payload.ExecutionId;
        if (string.IsNullOrEmpty(executionId) && !string.IsNullOrEmpty(attemptId))
            executionId = (await _offers.GetLatestByAttemptAsync(attemptId, ct))?.ExecutionId;

        if (string.IsNullOrEmpty(attemptId) || string.IsNullOrEmpty(executionId))
        {
            _logger.LogWarning("execution.commit without execution_id/execution_attempt_id (message {MessageId})", command.MessageId);
            return InboxCommandHandlerResult.Dead("INVALID_COMMIT_ENVELOPE");
        }

        // === Idempotência: commit-duplicate (seção 17) ===
        var existingAccepted = await _commits.GetAcceptedByAttemptAsync(attemptId, ct);
        if (existingAccepted is not null)
        {
            await _commits.SaveAsync(new ExecutionCommitRecord
            {
                CommitMessageId = command.MessageId,
                ExecutionId = executionId,
                ExecutionAttemptId = attemptId,
                ReservationId = existingAccepted.ReservationId,
                Accepted = false,
                RejectionReason = "DUPLICATE_ATTEMPT_COMMIT",
                ReceivedAtUtc = command.ReceivedAtUtc,
                ProcessedAtUtc = _clock.UtcNow
            }, ct);
            _logger.LogInformation("Duplicate execution.commit for attempt {AttemptId}; execution already committed.", attemptId);
            return InboxCommandHandlerResult.Processed("duplicate_commit");
        }

        var execution = await _execRepo.GetAsync(executionId, ct);
        if (execution is null)
        {
            return InboxCommandHandlerResult.Dead("EXECUTION_NOT_FOUND");
        }

        if (execution.CurrentState != ExecutionState.Reserved)
        {
            if (execution.CurrentState == ExecutionState.Offered)
            {
                // Nunca deveria acontecer: o offer handler transiciona
                // Offered->Reserved antes de responder accept. Chegar aqui
                // indica uma inconsistência de protocolo/estado local.
                return InboxCommandHandlerResult.Dead("EXECUTION_NOT_RESERVED");
            }

            // Estado já avançou (Committed em diante) — idempotente, não
            // reinicia a execução (seção 17).
            _logger.LogInformation("execution.commit for attempt {AttemptId} arrived after state already advanced to {State}; treating as idempotent.",
                attemptId, execution.CurrentState);
            return InboxCommandHandlerResult.Processed($"already_{execution.CurrentState}");
        }

        var reservationId = execution.ReservationId;
        if (string.IsNullOrEmpty(reservationId))
        {
            return InboxCommandHandlerResult.Dead("MISSING_RESERVATION_ID");
        }

        // === Commit atômico com proteção contra a race de expiração (seção 14-16) ===
        var reservation = await _reservations.TryCommitAsync(reservationId, ct);
        if (reservation is null)
        {
            return InboxCommandHandlerResult.Dead("RESERVATION_NOT_FOUND");
        }

        if (reservation.Status != ReservationStatus.Committed)
        {
            var reasonCode = reservation.Status switch
            {
                ReservationStatus.Expired => "RESERVATION_EXPIRED",
                _ => "RESERVATION_NOT_AVAILABLE"
            };

            await _commits.SaveAsync(new ExecutionCommitRecord
            {
                CommitMessageId = command.MessageId,
                ExecutionId = executionId,
                ExecutionAttemptId = attemptId,
                ReservationId = reservationId,
                Accepted = false,
                RejectionReason = reasonCode,
                ReceivedAtUtc = command.ReceivedAtUtc,
                ProcessedAtUtc = _clock.UtcNow
            }, ct);

            // A tentativa está morta: não criamos reserva nova automaticamente
            // (seção 16). Libera locks de desktop se houver (best-effort) e
            // encerra a execução localmente; cabe ao Portal decidir se cria
            // uma nova tentativa.
            if (ExecutionStateMachine.CanTransition(execution.CurrentState, ExecutionState.Cancelled))
                await ExecutionTransitions.TransitionAsync(_execRepo, _clock, execution, ExecutionState.Cancelled, ct);

            if (_desktopLocks is not null)
            {
                try { await _desktopLocks.ReleaseAsync(executionId, attemptId, CancellationToken.None); }
                catch (Exception ex) { _logger.LogWarning(ex, "Failed to release desktop locks after commit rejection for {ExecutionId}/{AttemptId}", executionId, attemptId); }
            }

            await _outboxPublisher.EnqueueAsync(
                PortalMessageTypes.ExecutionCommitRejected,
                new ExecutionCommitRejectedPayload
                {
                    ExecutionOfferId = payload.ExecutionOfferId,
                    ExecutionAttemptId = attemptId,
                    ReasonCode = reasonCode,
                    Details = $"Reservation {reservationId} is {reservation.Status} at commit time."
                },
                executionId: executionId,
                executionAttemptId: attemptId,
                ct: ct);

            _logger.LogWarning("execution.commit rejected for attempt {AttemptId}: reservation {ReservationId} is {Status}.",
                attemptId, reservationId, reservation.Status);

            return InboxCommandHandlerResult.Processed("commit_rejected");
        }

        await _commits.SaveAsync(new ExecutionCommitRecord
        {
            CommitMessageId = command.MessageId,
            ExecutionId = executionId,
            ExecutionAttemptId = attemptId,
            ReservationId = reservationId,
            Accepted = true,
            ReceivedAtUtc = command.ReceivedAtUtc,
            ProcessedAtUtc = _clock.UtcNow
        }, ct);

        await _leases.SaveAsync(new ExecutionLeaseRecord
        {
            LeaseId = payload.LeaseId,
            ExecutionId = executionId,
            ExecutionAttemptId = attemptId,
            State = LeaseState.Active,
            GrantedAtUtc = _clock.UtcNow,
            ExpiresAtUtc = payload.LeaseExpiresAt,
            LastRenewedAtUtc = _clock.UtcNow
        }, ct);

        await ExecutionTransitions.TransitionAsync(_execRepo, _clock, execution, ExecutionState.Committed, ct);

        // Resolve o manifesto novamente (o pacote já foi validado na oferta;
        // reler aqui evita manter estado grande em memória entre offer e commit).
        var artifact = await _packageStore.GetArtifactAsync(execution.AutomationVersionId ?? execution.AutomationId!, ct);
        if (artifact is null || !File.Exists(artifact.ManifestPath))
        {
            await FailCommittedExecutionAsync(execution, reservationId, "PACKAGE_NO_LONGER_AVAILABLE", ct);
            return InboxCommandHandlerResult.Processed("commit_failed_package_missing");
        }

        var validation = await _manifestValidator.ValidateAsync(artifact.ManifestPath, ct);
        if (!validation.IsValid || validation.Manifest is null)
        {
            await FailCommittedExecutionAsync(execution, reservationId, "MANIFEST_INVALID_AT_COMMIT", ct);
            return InboxCommandHandlerResult.Processed("commit_failed_manifest_invalid");
        }

        var manifest = validation.Manifest;

        await _outboxPublisher.EnqueueAsync(
            PortalMessageTypes.ExecutionPreparing,
            new { ExecutionId = executionId, ExecutionAttemptId = attemptId },
            executionId: executionId,
            executionAttemptId: attemptId,
            ct: ct);

        // Fire-and-forget deliberado: ExecuteAsync só retorna quando a
        // automação termina (background/browser podem rodar por horas). O
        // InboxCommandProcessor não pode ficar bloqueado esperando.
        _ = Task.Run(async () =>
        {
            try
            {
                var result = await _executionManager.ExecuteAsync(execution, manifest, execution.InputJson, CancellationToken.None);
                if (_artifactManager is not null && result.Artifacts.Count > 0)
                    await _artifactManager.RegisterAsync(executionId, attemptId, result.Artifacts, CancellationToken.None);

                var messageType = result.Success ? PortalMessageTypes.ExecutionCompleted : PortalMessageTypes.ExecutionFailed;
                await _outboxPublisher.EnqueueAsync(
                    messageType,
                    new
                    {
                        ExecutionId = executionId,
                        ExecutionAttemptId = attemptId,
                        Success = result.Success,
                        ExitCode = result.ExitCode,
                        Error = result.ErrorOutput,
                        CompletedAt = result.CompletedAtUtc
                    },
                    executionId: executionId,
                    executionAttemptId: attemptId);
            }
            catch (OperationCanceledException)
            {
                // ExecutionManager.ExecuteAsync relança OperationCanceledException
                // depois de transicionar a execução para Cancelled (via
                // ExecutionCancelRequestedHandler -> ExecutionManager.CancelAsync).
                // Reportar isso como execution.failed enganaria o Portal — o
                // evento correto aqui é execution.cancelled.
                _logger.LogInformation("Execution {ExecutionId}/{AttemptId} was cancelled.", executionId, attemptId);
                try
                {
                    await _outboxPublisher.EnqueueAsync(
                        PortalMessageTypes.ExecutionCancelled,
                        new { ExecutionId = executionId, ExecutionAttemptId = attemptId },
                        executionId: executionId,
                        executionAttemptId: attemptId);
                }
                catch (Exception outboxEx)
                {
                    _logger.LogError(outboxEx, "Failed to enqueue execution.cancelled after cancelled execution for {ExecutionId}/{AttemptId}.", executionId, attemptId);
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Unhandled exception while executing {ExecutionId}/{AttemptId} dispatched from execution.commit.", executionId, attemptId);
                try
                {
                    await _outboxPublisher.EnqueueAsync(
                        PortalMessageTypes.ExecutionFailed,
                        new { ExecutionId = executionId, ExecutionAttemptId = attemptId, Success = false, Error = ex.Message },
                        executionId: executionId,
                        executionAttemptId: attemptId);
                }
                catch (Exception outboxEx)
                {
                    _logger.LogError(outboxEx, "Failed to enqueue execution.failed after unhandled execution exception for {ExecutionId}/{AttemptId}.", executionId, attemptId);
                }
            }
        }, CancellationToken.None);

        _logger.LogInformation("execution.commit accepted: execution={ExecutionId}, attempt={AttemptId}; dispatching ExecutionManager.",
            executionId, attemptId);

        return InboxCommandHandlerResult.Processed("committed");
    }

    private async Task FailCommittedExecutionAsync(ExecutionRecord execution, string reservationId, string reasonCode, CancellationToken ct)
    {
        _logger.LogError("Failing committed execution {ExecutionId}: {ReasonCode}", execution.ExecutionId, reasonCode);

        if (ExecutionStateMachine.CanTransition(execution.CurrentState, ExecutionState.Failed))
            await ExecutionTransitions.TransitionAsync(_execRepo, _clock, execution, ExecutionState.Failed, ct);

        await _reservations.ReleaseAsync(reservationId, CancellationToken.None);

        if (_desktopLocks is not null)
        {
            try { await _desktopLocks.ReleaseAsync(execution.ExecutionId, execution.CurrentAttemptId ?? string.Empty, CancellationToken.None); }
            catch (Exception ex) { _logger.LogWarning(ex, "Failed to release desktop locks after commit-time failure for {ExecutionId}", execution.ExecutionId); }
        }

        await _outboxPublisher.EnqueueAsync(
            PortalMessageTypes.ExecutionFailed,
            new { ExecutionId = execution.ExecutionId, ExecutionAttemptId = execution.CurrentAttemptId, Success = false, Error = reasonCode },
            executionId: execution.ExecutionId,
            executionAttemptId: execution.CurrentAttemptId,
            ct: CancellationToken.None);
    }
}
