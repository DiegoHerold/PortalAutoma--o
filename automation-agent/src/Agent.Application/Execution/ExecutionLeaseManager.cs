using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Execution;
using Biason.AutomationAgent.Domain.StateMachines;
using Biason.AutomationAgent.Application.Messaging;
using Biason.AutomationAgent.Protocol.Messages;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace Biason.AutomationAgent.Application.Execution;

/// <summary>
/// Implementação de <see cref="IExecutionLeaseManager"/> (Bloco 5.5, seção
/// 9/19). Reaproveita <see cref="ExecutionTransitions"/> para as transições
/// de estado e <c>IExecutionManager.CancelAsync</c> para interromper a
/// execução quando um lease é perdido — mesma lógica de "salto direto vs.
/// sinalizar processo em execução" já usada por
/// <c>ExecutionCancelRequestedHandler</c> (Incremento 4), sem duplicá-la
/// (consulta <c>ExecutionStateMachine.CanTransition</c> diretamente).
/// </summary>
public sealed class ExecutionLeaseManager : IExecutionLeaseManager
{
    private readonly IExecutionLeaseRepository _leases;
    private readonly IExecutionRepository _execRepo;
    private readonly IResourceReservationManager _reservations;
    private readonly IExecutionManager _executionManager;
    private readonly OutboxMessagePublisher _outboxPublisher;
    private readonly IDesktopLockManager? _desktopLocks;
    private readonly IClock _clock;
    private readonly ExecutionOptions _options;
    private readonly ILogger<ExecutionLeaseManager> _logger;

    public ExecutionLeaseManager(
        IExecutionLeaseRepository leases,
        IExecutionRepository execRepo,
        IResourceReservationManager reservations,
        IExecutionManager executionManager,
        OutboxMessagePublisher outboxPublisher,
        IClock clock,
        IOptions<ExecutionOptions> options,
        ILogger<ExecutionLeaseManager> logger,
        IDesktopLockManager? desktopLocks = null)
    {
        _leases = leases;
        _execRepo = execRepo;
        _reservations = reservations;
        _executionManager = executionManager;
        _outboxPublisher = outboxPublisher;
        _clock = clock;
        _options = options.Value;
        _logger = logger;
        _desktopLocks = desktopLocks;
    }

    public async Task RenewDueLeasesAsync(CancellationToken ct = default)
    {
        var now = _clock.UtcNow;
        var leases = await _leases.GetNonFinalAsync(ct);

        foreach (var lease in leases)
        {
            if (lease.ExpiresAtUtc <= now)
            {
                await HandleOverdueAsync(lease, now, ct);
                continue;
            }

            if (lease.State == LeaseState.Active && lease.ExpiresAtUtc <= now.AddSeconds(_options.LeaseRenewBeforeExpirySeconds))
            {
                await RequestRenewalAsync(lease, ct);
            }
        }
    }

    public async Task HandleLeaseGrantedAsync(string leaseId, string executionAttemptId, DateTime expiresAtUtc, CancellationToken ct = default)
    {
        var lease = await _leases.GetAsync(leaseId, ct) ?? await _leases.GetByAttemptAsync(executionAttemptId, ct);
        if (lease is null)
        {
            // Sem um ExecutionId local para associar, não há como criar um
            // registro de lease novo aqui (execution.lease_granted fora do
            // fluxo de commit não tem contrato publicado — ver
            // ExecutionLeasePayloads.cs). Loga e ignora em vez de arriscar
            // um registro inconsistente.
            _logger.LogWarning(
                "execution.lease_renewed/granted for unknown lease {LeaseId} / attempt {AttemptId}; ignoring.",
                leaseId, executionAttemptId);
            return;
        }

        lease.State = LeaseState.Active;
        lease.ExpiresAtUtc = expiresAtUtc;
        lease.LastRenewedAtUtc = _clock.UtcNow;
        lease.RenewAttemptCount = 0;
        await _leases.UpdateAsync(lease, ct);

        _logger.LogInformation("Lease {LeaseId} (execution {ExecutionId}) renewed until {ExpiresAt}.",
            lease.LeaseId, lease.ExecutionId, expiresAtUtc);
    }

    public async Task HandleLeaseExpiredAsync(string leaseId, string executionAttemptId, string? reason, CancellationToken ct = default)
    {
        var lease = await _leases.GetAsync(leaseId, ct) ?? await _leases.GetByAttemptAsync(executionAttemptId, ct);
        if (lease is null)
        {
            _logger.LogWarning(
                "execution.lease_expired for unknown lease {LeaseId} / attempt {AttemptId}; ignoring.",
                leaseId, executionAttemptId);
            return;
        }

        if (lease.State is LeaseState.Expired or LeaseState.Lost)
            return; // idempotente — já tratado

        lease.State = LeaseState.Expired;
        lease.LostAtUtc = _clock.UtcNow;
        lease.LostReason = reason ?? "PORTAL_LEASE_EXPIRED";
        await _leases.UpdateAsync(lease, ct);

        _logger.LogWarning(
            "Lease {LeaseId} for execution {ExecutionId} expired by Portal decision ({Reason}); cancelling execution.",
            lease.LeaseId, lease.ExecutionId, lease.LostReason);

        await CancelExecutionForLeaseLossAsync(lease, lease.LostReason, ct);
    }

    public async Task ReconcileOnBootAsync(CancellationToken ct = default)
    {
        var now = _clock.UtcNow;
        var leases = await _leases.GetNonFinalAsync(ct);

        foreach (var lease in leases)
        {
            var graceDeadline = lease.ExpiresAtUtc.AddSeconds(_options.LeaseGraceSeconds);
            if (now >= graceDeadline)
            {
                _logger.LogWarning(
                    "Lease {LeaseId} (execution {ExecutionId}) already past its grace deadline at boot; marking lost.",
                    lease.LeaseId, lease.ExecutionId);
                await MarkLostAsync(lease, "LEASE_EXPIRED_DURING_RESTART", ct);
            }
            // Ainda dentro do prazo (ou da tolerância): o LeaseRenewalService
            // cuida no próximo ciclo normal, nada a fazer aqui no boot.
        }
    }

    private async Task RequestRenewalAsync(ExecutionLeaseRecord lease, CancellationToken ct)
    {
        lease.State = LeaseState.AtRisk;
        lease.RenewAttemptCount++;
        await _leases.UpdateAsync(lease, ct);

        await _outboxPublisher.EnqueueAsync(
            PortalMessageTypes.LeaseRenew,
            new LeaseRenewRequestPayload
            {
                LeaseId = lease.LeaseId,
                ExecutionAttemptId = lease.ExecutionAttemptId,
                RenewalSequence = lease.RenewAttemptCount,
                Running = true,
                ObservedAt = _clock.UtcNow
            },
            executionId: lease.ExecutionId,
            executionAttemptId: lease.ExecutionAttemptId,
            ct: ct);

        _logger.LogInformation("Requested renewal for lease {LeaseId} (execution {ExecutionId}), attempt #{Attempt}.",
            lease.LeaseId, lease.ExecutionId, lease.RenewAttemptCount);
    }

    private async Task HandleOverdueAsync(ExecutionLeaseRecord lease, DateTime now, CancellationToken ct)
    {
        var graceDeadline = lease.ExpiresAtUtc.AddSeconds(_options.LeaseGraceSeconds);
        if (now < graceDeadline)
            return; // ainda dentro da tolerância, aguarda resposta do Portal

        await MarkLostAsync(lease, "LEASE_RENEWAL_TIMEOUT", ct);
    }

    private async Task MarkLostAsync(ExecutionLeaseRecord lease, string reason, CancellationToken ct)
    {
        if (lease.State == LeaseState.Lost)
            return; // idempotente

        lease.State = LeaseState.Lost;
        lease.LostAtUtc = _clock.UtcNow;
        lease.LostReason = reason;
        await _leases.UpdateAsync(lease, ct);

        await _outboxPublisher.EnqueueAsync(
            PortalMessageTypes.LeaseLost,
            new LeaseLostPayload { LeaseId = lease.LeaseId, ExecutionAttemptId = lease.ExecutionAttemptId, Reason = reason },
            executionId: lease.ExecutionId,
            executionAttemptId: lease.ExecutionAttemptId,
            ct: ct);

        _logger.LogWarning("Lease {LeaseId} for execution {ExecutionId} marked as lost ({Reason}); cancelling execution.",
            lease.LeaseId, lease.ExecutionId, reason);

        await CancelExecutionForLeaseLossAsync(lease, reason, ct);
    }

    private async Task CancelExecutionForLeaseLossAsync(ExecutionLeaseRecord lease, string reason, CancellationToken ct)
    {
        var execution = await _execRepo.GetAsync(lease.ExecutionId, ct);
        if (execution is null || ExecutionStateMachine.IsTerminal(execution.CurrentState))
            return;

        if (ExecutionStateMachine.CanTransition(execution.CurrentState, ExecutionState.Cancelled))
        {
            await ExecutionTransitions.TransitionAsync(_execRepo, _clock, execution, ExecutionState.Cancelled, ct);

            if (execution.ReservationId is not null)
                await _reservations.ReleaseAsync(execution.ReservationId, CancellationToken.None);

            if (_desktopLocks is not null)
            {
                try { await _desktopLocks.ReleaseAsync(execution.ExecutionId, execution.CurrentAttemptId ?? string.Empty, CancellationToken.None); }
                catch (Exception ex) { _logger.LogWarning(ex, "Failed to release desktop locks after lease loss for {ExecutionId}", execution.ExecutionId); }
            }
        }

        // Best-effort: cobre Running (sinaliza o processo/token) e o caso de
        // Starting já ter lançado um processo, exatamente como
        // ExecutionCancelRequestedHandler faz para cancelamento remoto.
        await _executionManager.CancelAsync(execution.ExecutionId, CancellationToken.None);
    }
}
