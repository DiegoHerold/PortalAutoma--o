using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models;
using Biason.AutomationAgent.Domain.Models.Execution;
using Biason.AutomationAgent.Domain.StateMachines;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
// Ver ILauncher.cs: alias necessário por colisão com System.Threading.ExecutionContext.
using ExecutionContext = Biason.AutomationAgent.Domain.Models.Execution.ExecutionContext;

namespace Biason.AutomationAgent.Application.Execution;

public sealed class ExecutionManager : IExecutionManager
{
    private readonly IExecutionRepository _execRepo;
    private readonly IExecutionAttemptRepository _attemptRepo;
    private readonly IAdmissionController _admission;
    private readonly ICapacityManager _capacity;
    private readonly IResourceReservationManager _reservations;
    private readonly IWorkspaceManager _workspace;
    private readonly IProcessManager _processManager;
    private readonly ICancellationManager _cancellation;
    private readonly IResultCollector _results;
    private readonly IRuntimeStore _runtimeStore;
    private readonly IPackageStore _packageStore;
    private readonly IEnumerable<ILauncher> _launchers;
    private readonly IClock _clock;
    private readonly ExecutionOptions _options;
    private readonly ILogger<ExecutionManager> _logger;
    private readonly IInteractiveExecutionCoordinator? _interactiveCoordinator;

    private readonly Dictionary<string, ProcessHandle> _activeProcesses = new();
    private readonly object _lock = new();

    public ExecutionManager(
        IExecutionRepository execRepo,
        IExecutionAttemptRepository attemptRepo,
        IAdmissionController admission,
        ICapacityManager capacity,
        IResourceReservationManager reservations,
        IWorkspaceManager workspace,
        IProcessManager processManager,
        ICancellationManager cancellation,
        IResultCollector results,
        IRuntimeStore runtimeStore,
        IPackageStore packageStore,
        IEnumerable<ILauncher> launchers,
        IClock clock,
        IOptions<ExecutionOptions> options,
        ILogger<ExecutionManager> logger,
        IInteractiveExecutionCoordinator? interactiveCoordinator = null)
    {
        _execRepo = execRepo;
        _attemptRepo = attemptRepo;
        _admission = admission;
        _capacity = capacity;
        _reservations = reservations;
        _workspace = workspace;
        _processManager = processManager;
        _cancellation = cancellation;
        _results = results;
        _runtimeStore = runtimeStore;
        _packageStore = packageStore;
        _launchers = launchers;
        _clock = clock;
        _options = options.Value;
        _logger = logger;
        _interactiveCoordinator = interactiveCoordinator;
    }

    public async Task<ExecutionResult> ExecuteAsync(ExecutionRecord execution, AutomationManifest manifest, string? inputJson, CancellationToken ct = default)
    {
        var attemptId = $"att_{Guid.NewGuid():N}";
        var pool = manifest.Resources?.Pool ?? PoolType.Background;
        var timeoutSeconds = manifest.Timeout?.ExecutionSeconds ?? _options.DefaultTimeoutSeconds;

        if (IsInteractive(manifest, pool))
        {
            if (_interactiveCoordinator is null)
                return new ExecutionResult
                {
                    ExecutionId = execution.ExecutionId,
                    AttemptId = attemptId,
                    Success = false,
                    ErrorOutput = "Interactive execution services are not registered.",
                    CompletedAtUtc = _clock.UtcNow
                };

            return await _interactiveCoordinator.ExecuteAsync(execution, manifest, attemptId, inputJson, ct);
        }

        // Transition: Committed → Preparing
        await TransitionAsync(execution, ExecutionState.Preparing, "Preparing execution");

        ExecutionAttempt? attempt = null;
        string? workspacePath = null;

        try
        {
            // Create attempt record
            attempt = new ExecutionAttempt
            {
                AttemptId = attemptId,
                ExecutionId = execution.ExecutionId,
                AttemptNumber = execution.AttemptCount + 1,
                CurrentState = ExecutionState.Preparing,
                Pool = pool,
                CreatedAtUtc = _clock.UtcNow
            };
            await _attemptRepo.SaveAsync(attempt, ct);

            execution.AttemptCount++;
            execution.CurrentAttemptId = attemptId;

            // Resolve runtime and package
            var runtimeId = manifest.Runtime.Id;
            var runtimeVersion = manifest.Runtime.Version ?? "latest";
            var runtimePath = _runtimeStore.GetPath(runtimeId, runtimeVersion)
                ?? throw new InvalidOperationException($"Runtime not found: {runtimeId}:{runtimeVersion}");

            var packagePath = _packageStore.GetPath(execution.AutomationVersionId ?? execution.AutomationId!)
                ?? throw new InvalidOperationException($"Package not found for automation {execution.AutomationId}");

            // Create workspace
            workspacePath = _workspace.CreateWorkspace(execution.ExecutionId, attemptId);
            execution.WorkspacePath = workspacePath;
            attempt.WorkspacePath = workspacePath;

            // Write input
            if (inputJson is not null)
            {
                var inputPath = Path.Combine(workspacePath, "input", "input.json");
                await File.WriteAllTextAsync(inputPath, inputJson, ct);
            }

            // Build execution context
            var execContext = new ExecutionContext
            {
                ExecutionId = execution.ExecutionId,
                AttemptId = attemptId,
                AutomationId = execution.AutomationId!,
                AutomationVersionId = execution.AutomationVersionId ?? execution.AutomationId!,
                Manifest = manifest,
                WorkspacePath = workspacePath,
                RuntimePath = runtimePath,
                PackagePath = packagePath,
                Pool = pool,
                TimeoutSeconds = timeoutSeconds,
                GracefulShutdownSeconds = manifest.Timeout?.GracefulShutdownSeconds ?? _options.GracefulShutdownSeconds,
                EnvironmentVariables = manifest.Environment ?? new(),
                InputJson = inputJson,
                CancellationToken = ct
            };

            // Transition: Preparing → Starting
            await TransitionAsync(execution, ExecutionState.Starting, "Launching process");
            attempt.CurrentState = ExecutionState.Starting;

            // Create cancellation with timeout
            using var cts = _cancellation.CreateLinked(execution.ExecutionId, timeoutSeconds, ct);

            // Launch process
            var processHandle = await _processManager.LaunchAsync(execContext, cts.Token);
            execution.ProcessId = processHandle.ProcessId;
            attempt.ProcessId = processHandle.ProcessId;
            attempt.StartedAtUtc = _clock.UtcNow;

            lock (_lock) { _activeProcesses[execution.ExecutionId] = processHandle; }

            // Move used slot from reserved to used
            _capacity.IncrementUsed(pool);

            // Transition: Starting → Running
            await TransitionAsync(execution, ExecutionState.Running, "Process running");
            attempt.CurrentState = ExecutionState.Running;
            await _attemptRepo.UpdateAsync(attempt, ct);

            // Wait for process to exit
            await processHandle.Process.WaitForExitAsync(cts.Token);
            var exitCode = processHandle.Process.ExitCode;

            attempt.ExitCode = exitCode;
            attempt.CompletedAtUtc = _clock.UtcNow;

            // Collect results
            var result = await _results.CollectAsync(execution.ExecutionId, attemptId, workspacePath, exitCode, ct);

            // Transition to final state
            if (exitCode == 0)
            {
                await TransitionAsync(execution, ExecutionState.Succeeded, "Execution completed successfully");
                attempt.CurrentState = ExecutionState.Succeeded;
            }
            else
            {
                await TransitionAsync(execution, ExecutionState.Failed, $"Process exited with code {exitCode}");
                attempt.CurrentState = ExecutionState.Failed;
                attempt.ErrorMessage = $"Exit code: {exitCode}";
            }

            await _attemptRepo.UpdateAsync(attempt, ct);
            return result;
        }
        catch (OperationCanceledException) when (ct.IsCancellationRequested)
        {
            await TransitionAsync(execution, ExecutionState.Cancelled, "Cancelled by agent");
            if (attempt is not null) { attempt.CurrentState = ExecutionState.Cancelled; await _attemptRepo.UpdateAsync(attempt, ct); }
            throw;
        }
        catch (OperationCanceledException)
        {
            // Timeout
            await TransitionAsync(execution, ExecutionState.TimedOut, $"Timed out after {timeoutSeconds}s");
            if (attempt is not null) { attempt.CurrentState = ExecutionState.TimedOut; attempt.ErrorMessage = "Timeout"; await _attemptRepo.UpdateAsync(attempt, CancellationToken.None); }
            return new ExecutionResult { ExecutionId = execution.ExecutionId, AttemptId = attemptId, Success = false, ErrorOutput = "Execution timed out", CompletedAtUtc = _clock.UtcNow };
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Execution {ExecutionId} failed", execution.ExecutionId);
            await TransitionAsync(execution, ExecutionState.Failed, ex.Message);
            if (attempt is not null) { attempt.CurrentState = ExecutionState.Failed; attempt.ErrorMessage = ex.Message; await _attemptRepo.UpdateAsync(attempt, CancellationToken.None); }
            return new ExecutionResult { ExecutionId = execution.ExecutionId, AttemptId = attemptId, Success = false, ErrorOutput = ex.Message, CompletedAtUtc = _clock.UtcNow };
        }
        finally
        {
            // Cleanup
            lock (_lock) { _activeProcesses.Remove(execution.ExecutionId); }
            _cancellation.Remove(execution.ExecutionId);
            _capacity.DecrementUsed(pool);

            if (execution.ReservationId is not null)
                await _reservations.ReleaseAsync(execution.ReservationId, CancellationToken.None);

            // Touch package LRU
            if (execution.AutomationVersionId is not null)
                await _packageStore.TouchLastUsedAsync(execution.AutomationVersionId, CancellationToken.None);
        }
    }

    public async Task CancelAsync(string executionId, CancellationToken ct = default)
    {
        await _cancellation.RequestCancellationAsync(executionId, ct);
        if (_interactiveCoordinator is not null)
            await _interactiveCoordinator.CancelAsync(executionId, ct);

        ProcessHandle? handle;
        lock (_lock) { _activeProcesses.TryGetValue(executionId, out handle); }

        if (handle is not null && _processManager.IsRunning(handle))
        {
            await _processManager.TerminateAsync(handle, _options.GracefulShutdownSeconds * 1000, ct);
        }
    }

    private static bool IsInteractive(AutomationManifest manifest, PoolType pool) =>
        pool == PoolType.Interactive ||
        string.Equals(manifest.Execution?.Mode, "interactive", StringComparison.OrdinalIgnoreCase);

    public Task<IReadOnlyList<ExecutionRecord>> GetActiveExecutionsAsync(CancellationToken ct = default)
        => _execRepo.GetActiveAsync(ct);

    public async Task RecoverOrphanedAsync(CancellationToken ct = default)
    {
        var active = await _execRepo.GetActiveAsync(ct);
        foreach (var exec in active)
        {
            // If we have no process handle for an active execution, it's orphaned from a previous instance
            bool hasProcess;
            lock (_lock) { hasProcess = _activeProcesses.ContainsKey(exec.ExecutionId); }

            if (!hasProcess && !ExecutionStateMachine.IsTerminal(exec.CurrentState))
            {
                _logger.LogWarning("Marking orphaned execution {ExecutionId} (was in state {State})",
                    exec.ExecutionId, exec.CurrentState);

                if (ExecutionStateMachine.CanTransition(exec.CurrentState, ExecutionState.Interrupted))
                {
                    await TransitionAsync(exec, ExecutionState.Interrupted, "Agent restarted — execution interrupted");
                    await TransitionAsync(exec, ExecutionState.Orphaned, "Orphaned after agent restart");
                }
            }
        }
    }

    private async Task TransitionAsync(ExecutionRecord exec, ExecutionState to, string reason)
    {
        if (exec.CurrentState == to) return;
        ExecutionStateMachine.ValidateTransition(exec.CurrentState, to);
        exec.PreviousState = exec.CurrentState;
        exec.CurrentState = to;
        exec.LastTransitionUtc = _clock.UtcNow;
        await _execRepo.UpdateStateAsync(exec.ExecutionId, exec, CancellationToken.None);
    }
}
