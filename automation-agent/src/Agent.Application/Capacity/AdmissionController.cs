using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models;
using Biason.AutomationAgent.Domain.Models.Capacity;
using Biason.AutomationAgent.Domain.Models.Interactive;
using Biason.AutomationAgent.Domain.Models.Sessions;
using Biason.AutomationAgent.Application.Interactive;
using Microsoft.Extensions.Logging;

namespace Biason.AutomationAgent.Application.Capacity;

public sealed class AdmissionController : IAdmissionController
{
    private readonly ICapacityManager _capacity;
    private readonly IResourceReservationManager _reservations;
    private readonly ICapabilityRepository _capabilities;
    private readonly IAgentStateManager _stateManager;
    private readonly ILogger<AdmissionController> _logger;
    private readonly IInteractiveSessionSelector? _interactiveSessionSelector;
    private readonly ISessionCapabilityService? _sessionCapabilities;
    private readonly IInteractivePoolService? _interactivePool;
    private readonly IDesktopLockManager? _desktopLocks;
    private readonly IInteractiveExecutionAssignmentRepository? _interactiveAssignments;
    private readonly IApplicationProcessInspector? _applicationProcesses;
    private readonly Domain.Configuration.InteractiveExecutionOptions? _interactiveOptions;

    public AdmissionController(
        ICapacityManager capacity,
        IResourceReservationManager reservations,
        ICapabilityRepository capabilities,
        IAgentStateManager stateManager,
        ILogger<AdmissionController> logger,
        IInteractiveSessionSelector? interactiveSessionSelector = null,
        ISessionCapabilityService? sessionCapabilities = null,
        IInteractivePoolService? interactivePool = null,
        IDesktopLockManager? desktopLocks = null,
        IInteractiveExecutionAssignmentRepository? interactiveAssignments = null,
        IApplicationProcessInspector? applicationProcesses = null,
        Microsoft.Extensions.Options.IOptions<Domain.Configuration.InteractiveExecutionOptions>? interactiveOptions = null)
    {
        _capacity = capacity;
        _reservations = reservations;
        _capabilities = capabilities;
        _stateManager = stateManager;
        _logger = logger;
        _interactiveSessionSelector = interactiveSessionSelector;
        _sessionCapabilities = sessionCapabilities;
        _interactivePool = interactivePool;
        _desktopLocks = desktopLocks;
        _interactiveAssignments = interactiveAssignments;
        _applicationProcesses = applicationProcesses;
        _interactiveOptions = interactiveOptions?.Value;
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
        var interactive = IsInteractive(manifest, pool);
        if (interactive)
        {
            pool = PoolType.Interactive;
            slots = 1;
        }

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
                return Reject(manifest, "INTERACTIVE_CAPABILITY_NOT_AVAILABLE", $"Missing capabilities: {string.Join(", ", missing)}");
            }
        }

        if (interactive)
            return await EvaluateInteractiveAsync(execution, manifest, pool, slots, ct);

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

    private async Task<AdmissionDecision> EvaluateInteractiveAsync(
        ExecutionRecord execution,
        AutomationManifest manifest,
        PoolType pool,
        int slots,
        CancellationToken ct)
    {
        if (_interactiveSessionSelector is null ||
            _sessionCapabilities is null ||
            _interactivePool is null ||
            _desktopLocks is null ||
            _interactiveAssignments is null)
        {
            return Reject(manifest, "INTERACTIVE_SESSION_NOT_AVAILABLE", "Interactive services are not registered.");
        }

        var selection = await _interactiveSessionSelector.SelectAsync(BuildSelectionRequest(manifest), ct);
        if (!selection.Success || selection.Session is null)
            return Reject(manifest, MapSelectionRejection(selection.RejectionCode), selection.RejectionReason ?? "No usable interactive session.");

        var session = selection.Session;
        if (session.SessionRunnerInstanceId is null)
            return Reject(manifest, "SESSION_RUNNER_NOT_CONNECTED", $"Session {session.SessionId} has no connected Session Runner.");

        if (session.State is WindowsSessionState.Disconnected or WindowsSessionState.Terminated)
            return Reject(manifest, "INTERACTIVE_SESSION_DISCONNECTED", $"Session {session.SessionId} is disconnected.");

        if (session.IsLocked == true || session.State == WindowsSessionState.Locked)
            return Reject(manifest, "INTERACTIVE_SESSION_LOCKED", $"Session {session.SessionId} is locked.");

        if (session.ScreenWidth is null || session.ScreenHeight is null || session.MonitorCount is null)
            return Reject(manifest, "DESKTOP_NOT_AVAILABLE", $"Session {session.SessionId} desktop details are unavailable.");

        if (!await _interactivePool.HasSlotAsync(session.SessionId, ct))
            return Reject(manifest, "INTERACTIVE_POOL_FULL", "Interactive pool has no available slot.");

        var requiredSessionCaps = RequiredInteractiveCapabilities(manifest);
        var availableSessionCaps = (await _sessionCapabilities.GetCapabilitiesAsync(ct))
            .Where(c => c.SessionId == session.SessionId && c.Status == CapabilityStatus.Available)
            .Select(c => c.Key)
            .ToHashSet(StringComparer.OrdinalIgnoreCase);

        var missingSessionCaps = requiredSessionCaps.Where(c => !availableSessionCaps.Contains(c)).ToArray();
        if (missingSessionCaps.Length > 0)
            return Reject(manifest, "INTERACTIVE_CAPABILITY_NOT_AVAILABLE", $"Missing session capabilities: {string.Join(", ", missingSessionCaps)}");

        var processPolicyRejection = await CheckApplicationProcessPoliciesAsync(manifest, session.SessionId, ct);
        if (processPolicyRejection is not null)
            return Reject(manifest, processPolicyRejection.Value.Code, processPolicyRejection.Value.Message);

        var attemptId = execution.CurrentAttemptId ?? $"att_{Guid.NewGuid():N}";
        var lockKeys = DesktopLockKeys.Normalize(session.SessionId, manifest.Resources?.ExclusiveResources);
        if (!await _desktopLocks.TryReserveAsync(execution.ExecutionId, attemptId, session.SessionId, lockKeys, ct))
            return Reject(manifest, "DESKTOP_RESOURCE_BUSY", "One or more desktop resources are already locked.");

        ResourceReservation reservation;
        try
        {
            reservation = await _reservations.ReserveAsync(execution.ExecutionId, pool, slots, ct);
        }
        catch (Exception ex)
        {
            await _desktopLocks.ReleaseAsync(execution.ExecutionId, attemptId, CancellationToken.None);
            return Reject(manifest, "INTERACTIVE_POOL_FULL", $"Reservation failed: {ex.Message}");
        }

        await _interactiveAssignments.SaveAsync(new InteractiveExecutionAssignment
        {
            ExecutionId = execution.ExecutionId,
            AttemptId = attemptId,
            SessionId = session.SessionId,
            SessionRunnerInstanceId = session.SessionRunnerInstanceId,
            ReservationId = reservation.ReservationId,
            Status = InteractiveExecutionStatus.Reserved,
            CreatedAtUtc = DateTime.UtcNow
        }, ct);

        _logger.LogInformation(
            "Interactive admission accepted: execution={ExecutionId}, attempt={AttemptId}, session={SessionId}, locks={Locks}",
            execution.ExecutionId, attemptId, session.SessionId, string.Join(",", lockKeys));

        return new AdmissionDecision
        {
            Accepted = true,
            ReservationId = reservation.ReservationId,
            Pool = pool,
            SlotsReserved = slots,
            SessionId = session.SessionId,
            SessionRunnerInstanceId = session.SessionRunnerInstanceId,
            ExecutionAttemptId = attemptId,
            ReservedLocks = lockKeys
        };
    }

    private static bool IsInteractive(AutomationManifest manifest, PoolType pool) =>
        pool == PoolType.Interactive ||
        string.Equals(manifest.Execution?.Mode, "interactive", StringComparison.OrdinalIgnoreCase);

    private static InteractiveSessionSelectionRequest BuildSelectionRequest(AutomationManifest manifest)
    {
        var policyText = manifest.Execution?.SessionPolicy ?? "active_unlocked";
        var policy = policyText.ToLowerInvariant() switch
        {
            "current_console_session" => InteractiveSessionSelectionPolicy.CurrentConsoleSession,
            "specific_session" => InteractiveSessionSelectionPolicy.SpecificSession,
            _ => InteractiveSessionSelectionPolicy.ActiveUnlocked
        };

        return new InteractiveSessionSelectionRequest
        {
            Policy = policy,
            SessionId = manifest.Execution?.SessionId
        };
    }

    private static IReadOnlyList<string> RequiredInteractiveCapabilities(AutomationManifest manifest)
    {
        var required = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            "interactive_session",
            "session_runner_connected",
            "desktop_available",
            "desktop_unlocked",
            "desktop_automation"
        };

        if (manifest.Capabilities?.Required is not null)
        {
            foreach (var cap in manifest.Capabilities.Required)
            {
                if (cap is "office.excel" or "dominio.installed")
                    required.Add(cap);
            }
        }

        return required.ToArray();
    }

    private async Task<(string Code, string Message)?> CheckApplicationProcessPoliciesAsync(AutomationManifest manifest, int sessionId, CancellationToken ct)
    {
        if (_applicationProcesses is null || _interactiveOptions is null)
            return null;

        var required = manifest.Capabilities?.Required ?? Array.Empty<string>();

        if (required.Any(c => string.Equals(c, "dominio.installed", StringComparison.OrdinalIgnoreCase)))
        {
            var running = await _applicationProcesses.FindExistingAsync("dominio.installed", sessionId, ct);
            if (running.Count > 0 && string.Equals(_interactiveOptions.DominioExistingProcessPolicy, "reject", StringComparison.OrdinalIgnoreCase))
                return ("DOMINIO_ALREADY_RUNNING", $"Dominio is already running in session {sessionId}.");
        }

        if (required.Any(c => string.Equals(c, "office.excel", StringComparison.OrdinalIgnoreCase)) &&
            string.Equals(_interactiveOptions.ExcelExistingProcessPolicy, "reject_if_conflicting", StringComparison.OrdinalIgnoreCase))
        {
            var running = await _applicationProcesses.FindExistingAsync("office.excel", sessionId, ct);
            if (running.Count > 0)
                return ("EXCEL_ALREADY_RUNNING", $"Excel is already running in session {sessionId}.");
        }

        return null;
    }

    private static string MapSelectionRejection(string? code) => code switch
    {
        "SESSION_RUNNER_MISSING" => "SESSION_RUNNER_NOT_CONNECTED",
        "SESSION_LOCKED" => "INTERACTIVE_SESSION_LOCKED",
        "SESSION_DISCONNECTED" => "INTERACTIVE_SESSION_DISCONNECTED",
        "DESKTOP_UNAVAILABLE" => "DESKTOP_NOT_AVAILABLE",
        _ => "INTERACTIVE_SESSION_NOT_AVAILABLE"
    };

    private AdmissionDecision Reject(AutomationManifest manifest, string reason)
        => Reject(manifest, "ADMISSION_REJECTED", reason);

    private AdmissionDecision Reject(AutomationManifest manifest, string code, string reason)
    {
        _logger.LogWarning("Admission rejected for {AutomationId}: {Reason}", manifest.Id, reason);
        return new AdmissionDecision
        {
            Accepted = false,
            RejectionCode = code,
            RejectionReason = reason,
            Pool = manifest.Resources?.Pool ?? PoolType.Background
        };
    }
}
