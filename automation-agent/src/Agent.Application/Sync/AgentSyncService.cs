using Biason.AutomationAgent.Application.Messaging;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Execution;
using Biason.AutomationAgent.Protocol.Messages;
using Microsoft.Extensions.Logging;

namespace Biason.AutomationAgent.Application.Sync;

public sealed class AgentSyncService : IAgentSyncService
{
    private readonly IAgentIdentityService _identity;
    private readonly IAgentStateManager _stateManager;
    private readonly IExecutionRepository _executions;
    private readonly IReservationRepository _reservations;
    private readonly IExecutionLeaseRepository _leases;
    private readonly IOutboxRepository _outbox;
    private readonly IInboxRepository _inbox;
    private readonly IPendingArtifactRepository _artifacts;
    private readonly ISyncRunRepository _syncRuns;
    private readonly OutboxMessagePublisher _outboxPublisher;
    private readonly IPortalConnectionManager? _connection;
    private readonly IInteractiveSessionRepository? _interactiveSessions;
    private readonly IClock _clock;
    private readonly ILogger<AgentSyncService> _logger;

    public AgentSyncService(
        IAgentIdentityService identity,
        IAgentStateManager stateManager,
        IExecutionRepository executions,
        IReservationRepository reservations,
        IExecutionLeaseRepository leases,
        IOutboxRepository outbox,
        IInboxRepository inbox,
        IPendingArtifactRepository artifacts,
        ISyncRunRepository syncRuns,
        OutboxMessagePublisher outboxPublisher,
        IClock clock,
        ILogger<AgentSyncService> logger,
        IPortalConnectionManager? connection = null,
        IInteractiveSessionRepository? interactiveSessions = null)
    {
        _identity = identity;
        _stateManager = stateManager;
        _executions = executions;
        _reservations = reservations;
        _leases = leases;
        _outbox = outbox;
        _inbox = inbox;
        _artifacts = artifacts;
        _syncRuns = syncRuns;
        _outboxPublisher = outboxPublisher;
        _clock = clock;
        _logger = logger;
        _connection = connection;
        _interactiveSessions = interactiveSessions;
    }

    public async Task PublishSyncStateAsync(string reason, string? correlationId = null, CancellationToken ct = default)
    {
        var syncRun = new SyncRunRecord
        {
            SyncId = $"sync_{Guid.NewGuid():N}",
            ConnectionId = _connection?.GetStatus().ConnectionId,
            StartedAtUtc = _clock.UtcNow,
            Status = "running"
        };

        await _syncRuns.SaveAsync(syncRun, ct);

        try
        {
            var identity = await _identity.GetIdentityAsync(ct);
            var activeExecutions = await _executions.GetActiveAsync(ct);
            var activeReservations = await _reservations.GetActiveAsync(ct);
            var nonFinalLeases = await _leases.GetNonFinalAsync(ct);
            var pendingArtifacts = await _artifacts.GetNonFinalAsync(limit: 100, ct);
            var outbox = await _outbox.GetDiagnosticsAsync(ct);
            var inbox = await _inbox.GetDiagnosticsAsync(ct);
            var sessions = _interactiveSessions is null
                ? Array.Empty<object>()
                : (await _interactiveSessions.GetAllAsync(ct)).Take(50).Cast<object>().ToArray();

            var payload = new AgentSyncStatePayload
            {
                AgentId = identity?.AgentId,
                InstanceId = identity?.InstanceId,
                AgentState = _stateManager.CurrentState.ToString(),
                Reason = reason,
                SentAt = _clock.UtcNow,
                RunningExecutions = activeExecutions.Select(e => new AgentSyncExecutionItem
                {
                    ExecutionId = e.ExecutionId,
                    ExecutionAttemptId = e.CurrentAttemptId,
                    State = e.CurrentState.ToString(),
                    ReservationId = e.ReservationId,
                    WorkspacePath = e.WorkspacePath
                }).ToArray(),
                Reservations = activeReservations.Select(r => new AgentSyncReservationItem
                {
                    ReservationId = r.ReservationId,
                    ExecutionId = r.ExecutionId,
                    Pool = r.Pool.ToString(),
                    Slots = r.Slots,
                    Status = r.Status.ToString(),
                    ExpiresAt = r.ExpiresAtUtc
                }).ToArray(),
                Leases = nonFinalLeases.Select(l => new AgentSyncLeaseItem
                {
                    LeaseId = l.LeaseId,
                    ExecutionId = l.ExecutionId,
                    ExecutionAttemptId = l.ExecutionAttemptId,
                    State = l.State,
                    ExpiresAt = l.ExpiresAtUtc
                }).ToArray(),
                InteractiveSessions = sessions,
                OutboxSummary = outbox,
                InboxSummary = inbox,
                PendingArtifacts = pendingArtifacts.Select(a => new AgentSyncArtifactItem
                {
                    ArtifactId = a.ArtifactId,
                    ExecutionId = a.ExecutionId,
                    ExecutionAttemptId = a.ExecutionAttemptId,
                    Name = a.Name,
                    Status = a.Status.ToString(),
                    SizeBytes = a.SizeBytes
                }).ToArray(),
                Reconciliation = BuildReconciliation(activeExecutions, activeReservations, nonFinalLeases).ToArray()
            };

            await _outboxPublisher.EnqueueAsync(
                PortalMessageTypes.SyncState,
                payload,
                correlationId: correlationId,
                ct: ct);

            syncRun.CompletedAtUtc = _clock.UtcNow;
            syncRun.RunningExecutionsReported = activeExecutions.Count;
            syncRun.LeasesReported = nonFinalLeases.Count;
            syncRun.OutboxPendingReported = outbox.Pending;
            syncRun.ReconciledCount = payload.Reconciliation.Count;
            syncRun.Status = "completed";
            await _syncRuns.CompleteAsync(syncRun, ct);

            _logger.LogInformation("Published agent.sync_state ({Reason}) with {ExecutionCount} active execution(s).",
                reason, activeExecutions.Count);
        }
        catch (Exception ex)
        {
            syncRun.CompletedAtUtc = _clock.UtcNow;
            syncRun.Status = "failed";
            syncRun.ErrorMessage = ex.Message;
            await _syncRuns.CompleteAsync(syncRun, CancellationToken.None);
            throw;
        }
    }

    private static IEnumerable<AgentSyncReconciliationItem> BuildReconciliation(
        IReadOnlyList<Domain.Models.ExecutionRecord> executions,
        IReadOnlyList<Domain.Models.Capacity.ResourceReservation> reservations,
        IReadOnlyList<ExecutionLeaseRecord> leases)
    {
        var reservationByExecution = reservations.ToDictionary(r => r.ExecutionId, StringComparer.Ordinal);
        var leaseByExecution = leases.ToDictionary(l => l.ExecutionId, StringComparer.Ordinal);

        foreach (var execution in executions)
        {
            if (execution.ReservationId is not null && !reservationByExecution.ContainsKey(execution.ExecutionId))
            {
                yield return new AgentSyncReconciliationItem
                {
                    ExecutionId = execution.ExecutionId,
                    Result = ExecutionReconciliationResult.RequiresIntervention,
                    Details = "Execution references a reservation that is not active locally."
                };
                continue;
            }

            if (leaseByExecution.TryGetValue(execution.ExecutionId, out var lease) &&
                lease.State is LeaseState.AtRisk or LeaseState.Lost)
            {
                yield return new AgentSyncReconciliationItem
                {
                    ExecutionId = execution.ExecutionId,
                    Result = ExecutionReconciliationResult.LocalAhead,
                    Details = $"Lease is {lease.State}; Portal reconciliation required."
                };
                continue;
            }

            yield return new AgentSyncReconciliationItem
            {
                ExecutionId = execution.ExecutionId,
                Result = ExecutionReconciliationResult.InSync
            };
        }
    }
}
