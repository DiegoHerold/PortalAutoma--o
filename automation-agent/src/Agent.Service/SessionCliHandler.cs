using System.Text.Json;
using Biason.AutomationAgent.Application.Sessions;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Sessions;

namespace Biason.AutomationAgent.Service;

public sealed class SessionCliHandler
{
    private readonly IInteractiveSessionRepository _interactiveSessions;
    private readonly ISessionRunnerRepository _sessionRunners;
    private readonly ISessionRunnerConnectionRepository _sessionRunnerConnections;
    private readonly IInteractiveSessionSelector _interactiveSessionSelector;
    private readonly ISessionCapabilityService _sessionCapabilityService;
    private readonly SessionRunnerPipeServer _sessionRunnerPipeServer;
    private readonly IInteractivePoolService _interactivePool;
    private readonly IDesktopLockManager _desktopLocks;
    private readonly IInteractiveExecutionAssignmentRepository _interactiveAssignments;
    private readonly IInteractiveExecutionProcessRepository _interactiveProcesses;
    private readonly IApplicationProcessOwnershipRepository _applicationProcesses;
    private readonly ICapabilityRepository _capabilities;
    private readonly IInteractiveExecutionCoordinator _interactiveCoordinator;

    private static readonly JsonSerializerOptions JsonOpts = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        WriteIndented = true
    };

    public SessionCliHandler(
        IInteractiveSessionRepository interactiveSessions,
        ISessionRunnerRepository sessionRunners,
        ISessionRunnerConnectionRepository sessionRunnerConnections,
        IInteractiveSessionSelector interactiveSessionSelector,
        ISessionCapabilityService sessionCapabilityService,
        SessionRunnerPipeServer sessionRunnerPipeServer,
        IInteractivePoolService interactivePool,
        IDesktopLockManager desktopLocks,
        IInteractiveExecutionAssignmentRepository interactiveAssignments,
        IInteractiveExecutionProcessRepository interactiveProcesses,
        IApplicationProcessOwnershipRepository applicationProcesses,
        ICapabilityRepository capabilities,
        IInteractiveExecutionCoordinator interactiveCoordinator)
    {
        _interactiveSessions = interactiveSessions;
        _sessionRunners = sessionRunners;
        _sessionRunnerConnections = sessionRunnerConnections;
        _interactiveSessionSelector = interactiveSessionSelector;
        _sessionCapabilityService = sessionCapabilityService;
        _sessionRunnerPipeServer = sessionRunnerPipeServer;
        _interactivePool = interactivePool;
        _desktopLocks = desktopLocks;
        _interactiveAssignments = interactiveAssignments;
        _interactiveProcesses = interactiveProcesses;
        _applicationProcesses = applicationProcesses;
        _capabilities = capabilities;
        _interactiveCoordinator = interactiveCoordinator;
    }

    public static bool IsSessionCommand(IEnumerable<string> args)
    {
        var values = args as string[] ?? args.ToArray();
        return values.Contains("session", StringComparer.OrdinalIgnoreCase)
            || values.Contains("session-runner", StringComparer.OrdinalIgnoreCase)
            || values.Contains("pipe", StringComparer.OrdinalIgnoreCase)
            || values.Contains("interactive", StringComparer.OrdinalIgnoreCase)
            || values.Contains("desktop", StringComparer.OrdinalIgnoreCase)
            || values.Contains("excel", StringComparer.OrdinalIgnoreCase)
            || values.Contains("dominio", StringComparer.OrdinalIgnoreCase);
    }

    public async Task<bool> TryHandleAsync(string[] cliArgs, CancellationToken ct)
    {
        if (cliArgs.Contains("session", StringComparer.OrdinalIgnoreCase) &&
            cliArgs.Contains("list", StringComparer.OrdinalIgnoreCase))
        {
            Console.WriteLine(JsonSerializer.Serialize(await _interactiveSessions.GetAllAsync(ct), JsonOpts));
            return true;
        }

        if (cliArgs.Contains("session", StringComparer.OrdinalIgnoreCase) &&
            cliArgs.Contains("show", StringComparer.OrdinalIgnoreCase))
        {
            var idText = cliArgs.SkipWhile(a => !a.Equals("show", StringComparison.OrdinalIgnoreCase)).Skip(1).FirstOrDefault();
            var session = int.TryParse(idText, out var id)
                ? await _interactiveSessions.GetAsync(id, ct)
                : null;
            Console.WriteLine(JsonSerializer.Serialize(session, JsonOpts));
            return true;
        }

        if (cliArgs.Contains("session", StringComparer.OrdinalIgnoreCase) &&
            cliArgs.Contains("select", StringComparer.OrdinalIgnoreCase))
        {
            var selected = await _interactiveSessionSelector.SelectAsync(
                new InteractiveSessionSelectionRequest
                {
                    Policy = InteractiveSessionSelectionPolicy.ActiveUnlocked
                },
                ct);
            Console.WriteLine(JsonSerializer.Serialize(selected, JsonOpts));
            return true;
        }

        if (cliArgs.Contains("session", StringComparer.OrdinalIgnoreCase) &&
            cliArgs.Contains("capabilities", StringComparer.OrdinalIgnoreCase))
        {
            Console.WriteLine(JsonSerializer.Serialize(await _sessionCapabilityService.GetCapabilitiesAsync(ct), JsonOpts));
            return true;
        }

        if (cliArgs.Contains("session-runner", StringComparer.OrdinalIgnoreCase) &&
            (cliArgs.Contains("list", StringComparer.OrdinalIgnoreCase) || cliArgs.Contains("status", StringComparer.OrdinalIgnoreCase)))
        {
            var payload = new
            {
                runners = await _sessionRunners.GetAllAsync(ct),
                connections = await _sessionRunnerConnections.GetRecentAsync(20, ct)
            };
            Console.WriteLine(JsonSerializer.Serialize(payload, JsonOpts));
            return true;
        }

        if (cliArgs.Contains("pipe", StringComparer.OrdinalIgnoreCase) &&
            (cliArgs.Contains("status", StringComparer.OrdinalIgnoreCase) || cliArgs.Contains("test", StringComparer.OrdinalIgnoreCase)))
        {
            Console.WriteLine(JsonSerializer.Serialize(_sessionRunnerPipeServer.GetStatus(), JsonOpts));
            return true;
        }

        if (cliArgs.Contains("interactive", StringComparer.OrdinalIgnoreCase) &&
            cliArgs.Contains("status", StringComparer.OrdinalIgnoreCase))
        {
            var payload = new
            {
                active = await _interactivePool.CountActiveAsync(ct),
                assignments = await _interactiveAssignments.GetActiveAsync(ct),
                pipe = _sessionRunnerPipeServer.GetStatus()
            };
            Console.WriteLine(JsonSerializer.Serialize(payload, JsonOpts));
            return true;
        }

        if (cliArgs.Contains("interactive", StringComparer.OrdinalIgnoreCase) &&
            cliArgs.Contains("sessions", StringComparer.OrdinalIgnoreCase))
        {
            Console.WriteLine(JsonSerializer.Serialize(await _interactiveSessions.GetAllAsync(ct), JsonOpts));
            return true;
        }

        if (cliArgs.Contains("interactive", StringComparer.OrdinalIgnoreCase) &&
            cliArgs.Contains("locks", StringComparer.OrdinalIgnoreCase))
        {
            Console.WriteLine(JsonSerializer.Serialize(await _desktopLocks.GetAllAsync(ct), JsonOpts));
            return true;
        }

        if (cliArgs.Contains("interactive", StringComparer.OrdinalIgnoreCase) &&
            cliArgs.Contains("cancel", StringComparer.OrdinalIgnoreCase))
        {
            var executionId = cliArgs.SkipWhile(a => !a.Equals("cancel", StringComparison.OrdinalIgnoreCase)).Skip(1).FirstOrDefault();
            if (!string.IsNullOrWhiteSpace(executionId))
                await _interactiveCoordinator.CancelAsync(executionId, ct);
            Console.WriteLine(JsonSerializer.Serialize(new { cancelled = !string.IsNullOrWhiteSpace(executionId), execution_id = executionId }, JsonOpts));
            return true;
        }

        if (cliArgs.Contains("desktop", StringComparer.OrdinalIgnoreCase) &&
            cliArgs.Contains("status", StringComparer.OrdinalIgnoreCase))
        {
            var selected = await _interactiveSessionSelector.SelectAsync(new InteractiveSessionSelectionRequest
            {
                Policy = InteractiveSessionSelectionPolicy.ActiveUnlocked
            }, ct);
            Console.WriteLine(JsonSerializer.Serialize(new
            {
                selected,
                capabilities = await _sessionCapabilityService.GetCapabilitiesAsync(ct)
            }, JsonOpts));
            return true;
        }

        if (cliArgs.Contains("desktop", StringComparer.OrdinalIgnoreCase) &&
            cliArgs.Contains("screenshot", StringComparer.OrdinalIgnoreCase))
        {
            Console.WriteLine(JsonSerializer.Serialize(new
            {
                captured = false,
                reason = "manual screenshot capture is reserved for active interactive executions"
            }, JsonOpts));
            return true;
        }

        if (cliArgs.Contains("excel", StringComparer.OrdinalIgnoreCase) &&
            cliArgs.Contains("capability", StringComparer.OrdinalIgnoreCase))
        {
            Console.WriteLine(JsonSerializer.Serialize(await CapabilityPayloadAsync("office.excel", ct), JsonOpts));
            return true;
        }

        if (cliArgs.Contains("dominio", StringComparer.OrdinalIgnoreCase) &&
            cliArgs.Contains("capability", StringComparer.OrdinalIgnoreCase))
        {
            Console.WriteLine(JsonSerializer.Serialize(await CapabilityPayloadAsync("dominio.installed", ct), JsonOpts));
            return true;
        }

        return false;
    }

    private async Task<object> CapabilityPayloadAsync(string key, CancellationToken ct)
    {
        var global = (await _capabilities.GetAllAsync(ct)).FirstOrDefault(c => string.Equals(c.Key, key, StringComparison.OrdinalIgnoreCase));
        var session = (await _sessionCapabilityService.GetCapabilitiesAsync(ct)).Where(c => string.Equals(c.Key, key, StringComparison.OrdinalIgnoreCase));
        return new { key, global, session };
    }
}
