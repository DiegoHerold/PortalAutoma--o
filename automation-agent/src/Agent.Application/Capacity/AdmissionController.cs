using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models;
using Biason.AutomationAgent.Domain.Models.Capacity;
using Microsoft.Extensions.Logging;

namespace Biason.AutomationAgent.Application.Capacity;

public sealed class AdmissionController : IAdmissionController
{
    private readonly ICapacityManager _capacity;
    private readonly IResourceReservationManager _reservations;
    private readonly ICapabilityRepository _capabilities;
    private readonly IAgentStateManager _stateManager;
    private readonly ILogger<AdmissionController> _logger;

    public AdmissionController(
        ICapacityManager capacity,
        IResourceReservationManager reservations,
        ICapabilityRepository capabilities,
        IAgentStateManager stateManager,
        ILogger<AdmissionController> logger)
    {
        _capacity = capacity;
        _reservations = reservations;
        _capabilities = capabilities;
        _stateManager = stateManager;
        _logger = logger;
    }

    public async Task<AdmissionDecision> EvaluateAsync(ExecutionRecord execution, AutomationManifest manifest, CancellationToken ct = default)
    {
        // 1. Check agent state — must be Ready
        if (_stateManager.CurrentState != AgentState.Ready &&
            _stateManager.CurrentState != AgentState.Degraded)
        {
            return Reject(manifest, $"Agent state is {_stateManager.CurrentState}, not accepting executions");
        }

        // 2. Determine pool
        var pool = manifest.Resources?.Pool ?? PoolType.Background;
        var slots = manifest.Resources?.Slots ?? 1;

        // 3. Check required capabilities
        if (manifest.Capabilities?.Required is { Count: > 0 } required)
        {
            var available = await _capabilities.GetAllAsync(ct);
            var capabilityKeys = available
                .Where(c => c.Status == CapabilityStatus.Available)
                .Select(c => c.Key)
                .ToHashSet(StringComparer.OrdinalIgnoreCase);

            var missing = required.Where(r => !capabilityKeys.Contains(r)).ToList();
            if (missing.Count > 0)
            {
                return Reject(manifest, $"Missing capabilities: {string.Join(", ", missing)}");
            }
        }

        // 4. Check capacity
        if (!_capacity.HasAvailableSlots(pool, slots))
        {
            return Reject(manifest, $"No available slots in pool {pool} (need {slots})");
        }

        // 5. Reserve
        try
        {
            var reservation = await _reservations.ReserveAsync(execution.ExecutionId, pool, slots, ct);

            _logger.LogInformation("Admission accepted: execution={ExecutionId}, pool={Pool}, reservation={ReservationId}",
                execution.ExecutionId, pool, reservation.ReservationId);

            return new AdmissionDecision
            {
                Accepted = true,
                ReservationId = reservation.ReservationId,
                Pool = pool,
                SlotsReserved = slots
            };
        }
        catch (Exception ex)
        {
            return Reject(manifest, $"Reservation failed: {ex.Message}");
        }
    }

    private AdmissionDecision Reject(AutomationManifest manifest, string reason)
    {
        _logger.LogWarning("Admission rejected for {AutomationId}: {Reason}", manifest.Id, reason);
        return new AdmissionDecision
        {
            Accepted = false,
            RejectionReason = reason,
            Pool = manifest.Resources?.Pool ?? PoolType.Background
        };
    }
}
