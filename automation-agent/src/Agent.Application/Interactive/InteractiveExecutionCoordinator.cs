using System.Text.Json;
using Biason.AutomationAgent.Application.Sessions;
using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models;
using Biason.AutomationAgent.Domain.Models.Execution;
using Biason.AutomationAgent.Domain.Models.Interactive;
using Biason.AutomationAgent.Domain.Models.Sessions;
using Biason.AutomationAgent.Domain.StateMachines;
using Biason.AutomationAgent.Protocol.Local;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace Biason.AutomationAgent.Application.Interactive;

public sealed class InteractiveExecutionCoordinator : IInteractiveExecutionCoordinator
{
    private readonly IExecutionRepository _executions;
    private readonly IExecutionAttemptRepository _attempts;
    private readonly IAdmissionController _admission;
    private readonly ICapacityManager _capacity;
    private readonly IResourceReservationManager _reservations;
    private readonly IWorkspaceManager _workspace;
    private readonly IRuntimeStore _runtimeStore;
    private readonly IPackageStore _packageStore;
    private readonly IResultCollector _results;
    private readonly IInteractiveExecutionAssignmentRepository _assignments;
    private readonly IInteractiveSessionRepository _sessions;
    private readonly ISessionRunnerRegistry _runnerRegistry;
    private readonly IInteractiveExecutionTokenService _tokens;
    private readonly IDesktopLockManager _locks;
    private readonly SessionRunnerPipeServer _pipeServer;
    private readonly IClock _clock;
    private readonly ExecutionOptions _executionOptions;
    private readonly LocalProtocolOptions _localOptions;
    private readonly ILogger<InteractiveExecutionCoordinator> _logger;

    public InteractiveExecutionCoordinator(
        IExecutionRepository executions,
        IExecutionAttemptRepository attempts,
        IAdmissionController admission,
        ICapacityManager capacity,
        IResourceReservationManager reservations,
        IWorkspaceManager workspace,
        IRuntimeStore runtimeStore,
        IPackageStore packageStore,
        IResultCollector results,
        IInteractiveExecutionAssignmentRepository assignments,
        IInteractiveSessionRepository sessions,
        ISessionRunnerRegistry runnerRegistry,
        IInteractiveExecutionTokenService tokens,
        IDesktopLockManager locks,
        SessionRunnerPipeServer pipeServer,
        IClock clock,
        IOptions<ExecutionOptions> executionOptions,
        IOptions<LocalProtocolOptions> localOptions,
        ILogger<InteractiveExecutionCoordinator> logger)
    {
        _executions = executions;
        _attempts = attempts;
        _admission = admission;
        _capacity = capacity;
        _reservations = reservations;
        _workspace = workspace;
        _runtimeStore = runtimeStore;
        _packageStore = packageStore;
        _results = results;
        _assignments = assignments;
        _sessions = sessions;
        _runnerRegistry = runnerRegistry;
        _tokens = tokens;
        _locks = locks;
        _pipeServer = pipeServer;
        _clock = clock;
        _executionOptions = executionOptions.Value;
        _localOptions = localOptions.Value;
        _logger = logger;
    }

    public async Task<ExecutionResult> ExecuteAsync(
        ExecutionRecord execution,
        AutomationManifest manifest,
        string attemptId,
        string? inputJson,
        CancellationToken ct = default)
    {
        var timeoutSeconds = manifest.Execution?.TimeoutSeconds
            ?? manifest.Timeout?.ExecutionSeconds
            ?? _executionOptions.DefaultTimeoutSeconds;
        var gracefulSeconds = manifest.Execution?.GracefulCancellationSeconds
            ?? manifest.Timeout?.GracefulShutdownSeconds
            ?? _executionOptions.GracefulShutdownSeconds;

        execution.CurrentAttemptId = attemptId;
        var decision = await _admission.EvaluateAsync(execution, manifest, ct);
        if (!decision.Accepted)
        {
            await TransitionAsync(execution, ExecutionState.Rejected, decision.RejectionCode ?? decision.RejectionReason ?? "interactive admission rejected");
            return new ExecutionResult
            {
                ExecutionId = execution.ExecutionId,
                AttemptId = attemptId,
                Success = false,
                ErrorOutput = decision.RejectionReason,
                CompletedAtUtc = _clock.UtcNow
            };
        }

        execution.ReservationId = decision.ReservationId;
        await TransitionAsync(execution, ExecutionState.Preparing, "interactive.execution.preparing");

        var assignment = await _assignments.GetAsync(execution.ExecutionId, attemptId, ct)
            ?? throw new InvalidOperationException("Interactive admission did not create an assignment.");
        var session = await _sessions.GetAsync(assignment.SessionId, ct)
            ?? throw new InvalidOperationException($"Interactive session {assignment.SessionId} disappeared.");

        ExecutionAttempt? attempt = null;
        string? executionToken = null;

        try
        {
            attempt = new ExecutionAttempt
            {
                AttemptId = attemptId,
                ExecutionId = execution.ExecutionId,
                AttemptNumber = execution.AttemptCount + 1,
                CurrentState = ExecutionState.Preparing,
                Pool = PoolType.Interactive,
                CreatedAtUtc = _clock.UtcNow
            };
            await _attempts.SaveAsync(attempt, ct);
            execution.AttemptCount++;

            var runtimeId = manifest.Runtime.Id;
            var runtimeVersion = manifest.Runtime.Version ?? "latest";
            var runtimePath = _runtimeStore.GetPath(runtimeId, runtimeVersion)
                ?? throw new InvalidOperationException($"Runtime not found: {runtimeId}:{runtimeVersion}");
            var packagePath = _packageStore.GetPath(execution.AutomationVersionId ?? execution.AutomationId!)
                ?? throw new InvalidOperationException($"Package not found for automation {execution.AutomationId}");

            var workspacePath = _workspace.CreateWorkspace(execution.ExecutionId, attemptId);
            execution.WorkspacePath = workspacePath;
            attempt.WorkspacePath = workspacePath;

            if (inputJson is not null)
                await File.WriteAllTextAsync(Path.Combine(workspacePath, "input", "input.json"), inputJson, ct);

            await _assignments.UpdatePreparedPathsAsync(execution.ExecutionId, attemptId, workspacePath, runtimePath, packagePath, ct);
            await _locks.CommitAsync(execution.ExecutionId, attemptId, ct);

            if (!_runnerRegistry.TryGetSessionToken(assignment.SessionRunnerInstanceId, out var sessionToken))
                throw new InvalidOperationException("Session Runner token is not available; runner must reconnect.");

            var tokenExpires = _clock.UtcNow.AddMinutes(_localOptions.ExecutionTokenExpirationMinutes);
            executionToken = LocalExecutionToken.Issue(
                sessionToken,
                execution.ExecutionId,
                attemptId,
                assignment.SessionId,
                assignment.SessionRunnerInstanceId,
                tokenExpires);
            _tokens.Remember(new InteractiveExecutionToken
            {
                Token = executionToken,
                Fingerprint = SessionTokenHasher.Fingerprint(executionToken),
                ExecutionId = execution.ExecutionId,
                ExecutionAttemptId = attemptId,
                SessionId = assignment.SessionId,
                SessionRunnerInstanceId = assignment.SessionRunnerInstanceId,
                ExpiresAtUtc = tokenExpires
            });

            await TransitionAsync(execution, ExecutionState.Starting, "interactive.execution.starting");
            attempt.CurrentState = ExecutionState.Starting;
            await _attempts.UpdateAsync(attempt, ct);
            await _locks.ActivateAsync(execution.ExecutionId, attemptId, ct);
            _capacity.IncrementUsed(PoolType.Interactive);

            var hostPipeName = $"biason_agent_interactive_{execution.ExecutionId}_{attemptId}";
            var context = BuildInteractiveContext(session, assignment.SessionRunnerInstanceId);
            var payload = BuildStartPayload(
                execution,
                manifest,
                attemptId,
                executionToken,
                assignment,
                session,
                runtimePath,
                packagePath,
                workspacePath,
                hostPipeName,
                context,
                timeoutSeconds,
                gracefulSeconds);

            var result = await _pipeServer.StartInteractiveExecutionAsync(
                assignment.SessionRunnerInstanceId,
                assignment.SessionId,
                payload,
                TimeSpan.FromSeconds(timeoutSeconds + gracefulSeconds + 30),
                ct);

            attempt.CompletedAtUtc = _clock.UtcNow;
            attempt.ExitCode = result.ExitCode;
            execution.ProcessId = (await _assignments.GetAsync(execution.ExecutionId, attemptId, CancellationToken.None))?.ExecutionHostProcessId;

            if (result.Success)
            {
                await TransitionAsync(execution, ExecutionState.Succeeded, "interactive.execution.completed");
                attempt.CurrentState = ExecutionState.Succeeded;
            }
            else if (result.Cancelled)
            {
                await TransitionAsync(execution, ExecutionState.Cancelled, "interactive.execution.cancelled");
                attempt.CurrentState = ExecutionState.Cancelled;
                attempt.ErrorMessage = result.ErrorMessage;
            }
            else
            {
                await TransitionAsync(execution, ExecutionState.Failed, result.ErrorCode ?? "interactive execution failed");
                attempt.CurrentState = ExecutionState.Failed;
                attempt.ErrorMessage = result.ErrorMessage;
            }

            await _attempts.UpdateAsync(attempt, CancellationToken.None);
            var collected = await _results.CollectAsync(execution.ExecutionId, attemptId, workspacePath, result.ExitCode ?? (result.Success ? 0 : 1), CancellationToken.None);
            return result.Success ? collected : new ExecutionResult
            {
                ExecutionId = execution.ExecutionId,
                AttemptId = attemptId,
                Success = false,
                ExitCode = result.ExitCode,
                ErrorOutput = result.ErrorMessage,
                CompletedAtUtc = _clock.UtcNow
            };
        }
        catch (OperationCanceledException) when (ct.IsCancellationRequested)
        {
            await TransitionAsync(execution, ExecutionState.Cancelled, "interactive execution cancelled by Agent");
            if (attempt is not null)
            {
                attempt.CurrentState = ExecutionState.Cancelled;
                attempt.CompletedAtUtc = _clock.UtcNow;
                await _attempts.UpdateAsync(attempt, CancellationToken.None);
            }
            throw;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Interactive execution {ExecutionId}/{AttemptId} failed", execution.ExecutionId, attemptId);
            await TransitionAsync(execution, ExecutionState.Failed, ex.Message);
            await _assignments.MarkCompletedAsync(execution.ExecutionId, attemptId, InteractiveExecutionStatus.Failed, null, _clock.UtcNow, "INTERACTIVE_EXECUTION_FAILED", ex.Message, CancellationToken.None);
            if (attempt is not null)
            {
                attempt.CurrentState = ExecutionState.Failed;
                attempt.ErrorMessage = ex.Message;
                attempt.CompletedAtUtc = _clock.UtcNow;
                await _attempts.UpdateAsync(attempt, CancellationToken.None);
            }
            return new ExecutionResult
            {
                ExecutionId = execution.ExecutionId,
                AttemptId = attemptId,
                Success = false,
                ErrorOutput = ex.Message,
                CompletedAtUtc = _clock.UtcNow
            };
        }
        finally
        {
            if (executionToken is not null)
                _tokens.Expire(executionToken);
            _capacity.DecrementUsed(PoolType.Interactive);
            await _locks.ReleaseAsync(execution.ExecutionId, attemptId, CancellationToken.None);
            if (execution.ReservationId is not null)
                await _reservations.ReleaseAsync(execution.ReservationId, CancellationToken.None);
        }
    }

    public async Task CancelAsync(string executionId, CancellationToken ct = default)
    {
        var active = (await _assignments.GetActiveAsync(ct)).FirstOrDefault(a => a.ExecutionId == executionId);
        if (active is null)
            return;

        await _assignments.UpdateStatusAsync(executionId, active.AttemptId, InteractiveExecutionStatus.CancelRequested, _clock.UtcNow, null, "cancel requested", ct);
        await _pipeServer.CancelInteractiveExecutionAsync(
            active.SessionRunnerInstanceId,
            active.SessionId,
            new InteractiveExecutionCancelPayload
            {
                ExecutionId = executionId,
                ExecutionAttemptId = active.AttemptId,
                Reason = "cancel_requested"
            },
            ct);
    }

    private InteractiveExecutionStartPayload BuildStartPayload(
        ExecutionRecord execution,
        AutomationManifest manifest,
        string attemptId,
        string executionToken,
        InteractiveExecutionAssignment assignment,
        InteractiveSessionRecord session,
        string runtimePath,
        string packagePath,
        string workspacePath,
        string hostPipeName,
        InteractiveExecutionContext context,
        int timeoutSeconds,
        int gracefulSeconds)
    {
        var hostPath = ResolveExecutionHostPath();
        var runtimeVersion = manifest.Runtime.Version ?? "latest";
        var configJson = BuildExecutionHostConfigJson(
            execution,
            manifest,
            attemptId,
            executionToken,
            runtimePath,
            packagePath,
            workspacePath,
            hostPipeName,
            context,
            timeoutSeconds,
            gracefulSeconds);

        return new InteractiveExecutionStartPayload
        {
            ExecutionId = execution.ExecutionId,
            ExecutionAttemptId = attemptId,
            SessionId = assignment.SessionId,
            ExecutionToken = executionToken,
            ExecutionHost = new LocalExecutionHostReference
            {
                Executable = "ExecutionHost.exe",
                ResolvedPath = hostPath
            },
            RuntimeReference = new LocalRuntimeReference
            {
                Id = manifest.Runtime.Id,
                Version = runtimeVersion,
                ResolvedPath = runtimePath
            },
            PackageReference = new LocalPackageReference
            {
                AutomationId = execution.AutomationId ?? manifest.Id,
                Version = manifest.Version,
                ResolvedPath = packagePath
            },
            WorkspaceReference = $"{execution.ExecutionId}/{attemptId}",
            WorkspacePath = workspacePath,
            HostPipeName = hostPipeName,
            ExecutionHostConfigJson = configJson,
            InteractiveContext = context
        };
    }

    private static string BuildExecutionHostConfigJson(
        ExecutionRecord execution,
        AutomationManifest manifest,
        string attemptId,
        string executionToken,
        string runtimePath,
        string packagePath,
        string workspacePath,
        string hostPipeName,
        InteractiveExecutionContext context,
        int timeoutSeconds,
        int gracefulSeconds)
    {
        var config = new
        {
            execution_id = execution.ExecutionId,
            attempt_id = attemptId,
            automation_id = execution.AutomationId ?? manifest.Id,
            mode = "interactive",
            pipe_name = hostPipeName,
            token = executionToken,
            timeout_seconds = timeoutSeconds,
            graceful_shutdown_seconds = gracefulSeconds,
            entrypoint = new
            {
                type = manifest.Entrypoint.Type.ToString(),
                executable_path = (string?)null,
                arguments = manifest.Entrypoint.Args,
                module = manifest.Entrypoint.Module,
                callable = manifest.Entrypoint.Callable,
                script = manifest.Entrypoint.Script
            },
            paths = new
            {
                runtime_path = runtimePath,
                package_path = packagePath,
                workspace_path = workspacePath,
                input_path = Path.Combine(workspacePath, "input"),
                output_path = Path.Combine(workspacePath, "output"),
                artifacts_path = Path.Combine(workspacePath, "artifacts"),
                temp_path = Path.Combine(workspacePath, "temp"),
                logs_path = Path.Combine(workspacePath, "logs")
            },
            environment = manifest.Environment ?? new Dictionary<string, string>(),
            interactive_context = context
        };

        return JsonSerializer.Serialize(config, new JsonSerializerOptions
        {
            PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
            WriteIndented = false
        });
    }

    private static InteractiveExecutionContext BuildInteractiveContext(InteractiveSessionRecord session, string runnerInstanceId) => new()
    {
        SessionId = session.SessionId,
        SessionType = session.SessionType,
        DesktopResolution = session.ScreenWidth.HasValue && session.ScreenHeight.HasValue
            ? new DesktopResolution { Width = session.ScreenWidth.Value, Height = session.ScreenHeight.Value }
            : null,
        DpiScale = session.DpiScale,
        MonitorCount = session.MonitorCount,
        SessionRunnerInstanceId = runnerInstanceId,
        DesktopLocked = session.IsLocked == true
    };

    private string ResolveExecutionHostPath()
    {
        var candidates = new[]
        {
            Path.Combine(AppContext.BaseDirectory, "ExecutionHost.exe"),
            Path.Combine(AppContext.BaseDirectory, "..", "Agent.ExecutionHost", "ExecutionHost.exe"),
            Path.Combine(AppContext.BaseDirectory, "..", "Agent.ExecutionHost", "bin", "Debug", "net8.0", "win-x64", "ExecutionHost.exe"),
            Path.Combine(AppContext.BaseDirectory, "..", "Agent.ExecutionHost", "bin", "Release", "net8.0", "win-x64", "ExecutionHost.exe"),
            Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "Agent.ExecutionHost", "bin", "Debug", "net8.0", "win-x64", "ExecutionHost.exe"),
            Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "Agent.ExecutionHost", "bin", "Release", "net8.0", "win-x64", "ExecutionHost.exe"),
            Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "..", "artifacts", "publish", "AgentService", "ExecutionHost.exe"),
            Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "..", "artifacts", "publish", "ExecutionHost", "ExecutionHost.exe"),
        };

        foreach (var path in candidates)
        {
            var full = Path.GetFullPath(path);
            if (File.Exists(full) && Path.GetFileName(full).Equals("ExecutionHost.exe", StringComparison.OrdinalIgnoreCase))
                return full;
        }

        throw new InvalidOperationException($"ExecutionHost.exe not found. Searched: {string.Join(", ", candidates.Select(Path.GetFullPath))}");
    }

    private async Task TransitionAsync(ExecutionRecord exec, ExecutionState to, string reason)
    {
        if (exec.CurrentState == to)
            return;

        if (!ExecutionStateMachine.CanTransition(exec.CurrentState, to))
        {
            _logger.LogWarning("Skipping invalid transition for {ExecutionId}: {From}->{To}", exec.ExecutionId, exec.CurrentState, to);
            return;
        }

        exec.PreviousState = exec.CurrentState;
        exec.CurrentState = to;
        exec.LastTransitionUtc = _clock.UtcNow;
        await _executions.UpdateStateAsync(exec.ExecutionId, exec, CancellationToken.None);
    }
}
