using System.Collections.Concurrent;
using System.Diagnostics;
using System.IO.Pipes;
using System.Text.Json;
using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Protocol.Local;
using Biason.AutomationAgent.Protocol.Serialization;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace Biason.AutomationAgent.SessionRunner;

public sealed class InteractiveExecutionHostRunner
{
    private readonly IDesktopStateReader _desktop;
    private readonly SessionRunnerOptions _options;
    private readonly ILogger<InteractiveExecutionHostRunner> _logger;
    private readonly ConcurrentDictionary<string, RunningHost> _running = new(StringComparer.Ordinal);

    public InteractiveExecutionHostRunner(
        IDesktopStateReader desktop,
        IOptions<SessionRunnerOptions> options,
        ILogger<InteractiveExecutionHostRunner> logger)
    {
        _desktop = desktop;
        _options = options.Value;
        _logger = logger;
    }

    public async Task StartAsync(
        InteractiveExecutionStartPayload payload,
        string instanceId,
        string sessionToken,
        SessionRunnerPipeClient agentPipe,
        CancellationToken ct)
    {
        var key = Key(payload.ExecutionId, payload.ExecutionAttemptId);
        if (_running.ContainsKey(key))
        {
            await SendFailedAsync(payload, instanceId, sessionToken, agentPipe, "EXECUTION_ALREADY_RUNNING", "Attempt is already running.", ct);
            return;
        }

        if (!LocalExecutionToken.TryValidate(
                payload.ExecutionToken,
                sessionToken,
                payload.ExecutionId,
                payload.ExecutionAttemptId,
                payload.SessionId,
                instanceId,
                DateTime.UtcNow,
                out var tokenError))
        {
            await SendFailedAsync(payload, instanceId, sessionToken, agentPipe, tokenError ?? "INTERACTIVE_EXECUTION_TOKEN_INVALID", "Execution token rejected.", ct);
            return;
        }

        var ownSessionId = Process.GetCurrentProcess().SessionId;
        if (payload.SessionId != ownSessionId)
        {
            await SendFailedAsync(payload, instanceId, sessionToken, agentPipe, "SESSION_MISMATCH", $"Runner session is {ownSessionId}, payload session is {payload.SessionId}.", ct);
            return;
        }

        var desktop = _desktop.ReadCurrent();
        if (desktop.Available == false || desktop.Locked == true)
        {
            await SendFailedAsync(payload, instanceId, sessionToken, agentPipe, "DESKTOP_UNAVAILABLE", "Desktop is locked or unavailable.", ct);
            return;
        }

        var hostPath = ResolveExecutionHostPath(payload.ExecutionHost.ResolvedPath);
        var workspacePath = Path.GetFullPath(payload.WorkspacePath);
        var tempPath = Path.Combine(workspacePath, "temp");
        Directory.CreateDirectory(tempPath);
        Directory.CreateDirectory(Path.Combine(workspacePath, "logs"));
        Directory.CreateDirectory(Path.Combine(workspacePath, "artifacts"));

        var configPath = Path.Combine(tempPath, $"interactive_host_{Guid.NewGuid():N}.json");
        await File.WriteAllTextAsync(configPath, payload.ExecutionHostConfigJson, ct);

        using var hostCts = CancellationTokenSource.CreateLinkedTokenSource(ct);
        using var hostPipe = new NamedPipeServerStream(
            payload.HostPipeName,
            PipeDirection.InOut,
            1,
            PipeTransmissionMode.Byte,
            PipeOptions.Asynchronous);

        var psi = new ProcessStartInfo
        {
            FileName = hostPath,
            Arguments = $"--config \"{configPath}\" --pipe \"{payload.HostPipeName}\" --entrypoint-type interactive",
            WorkingDirectory = workspacePath,
            UseShellExecute = false,
            CreateNoWindow = true
        };
        psi.Environment["AUTOMATION_EXECUTION_ID"] = payload.ExecutionId;
        psi.Environment["AUTOMATION_ATTEMPT_ID"] = payload.ExecutionAttemptId;
        psi.Environment["AUTOMATION_INTERACTIVE_MODE"] = "true";

        var process = new Process { StartInfo = psi, EnableRaisingEvents = true };
        if (!process.Start())
        {
            await SendFailedAsync(payload, instanceId, sessionToken, agentPipe, "INTERACTIVE_HOST_START_FAILED", "ExecutionHost did not start.", ct);
            return;
        }

        var running = new RunningHost(process, hostCts);
        if (!_running.TryAdd(key, running))
        {
            TryKill(process);
            await SendFailedAsync(payload, instanceId, sessionToken, agentPipe, "EXECUTION_ALREADY_RUNNING", "Attempt is already running.", ct);
            return;
        }

        await agentPipe.SendInteractiveStatusAsync(instanceId, payload.SessionId, sessionToken, LocalMessageTypes.InteractiveExecutionStarted,
            new InteractiveExecutionStatusPayload
            {
                ExecutionId = payload.ExecutionId,
                ExecutionAttemptId = payload.ExecutionAttemptId,
                ProcessId = process.Id,
                Payload = new { pid = process.Id, session_id = ownSessionId }
            }, ct);

        _ = Task.Run(() => PumpHostPipeAsync(hostPipe, payload, instanceId, sessionToken, agentPipe, hostCts.Token), CancellationToken.None);
        _ = Task.Run(() => WatchProcessAsync(process, payload, instanceId, sessionToken, agentPipe, key, hostCts.Token), CancellationToken.None);
    }

    public async Task CancelAsync(
        InteractiveExecutionCancelPayload payload,
        string instanceId,
        int sessionId,
        string sessionToken,
        SessionRunnerPipeClient agentPipe,
        CancellationToken ct)
    {
        var key = Key(payload.ExecutionId, payload.ExecutionAttemptId);
        if (!_running.TryGetValue(key, out var running))
            return;

        running.Cancellation.Cancel();
        await agentPipe.SendInteractiveStatusAsync(instanceId, sessionId, sessionToken, LocalMessageTypes.InteractiveExecutionCancelled,
            new InteractiveExecutionStatusPayload
            {
                ExecutionId = payload.ExecutionId,
                ExecutionAttemptId = payload.ExecutionAttemptId,
                ProcessId = SafePid(running.Process),
                Message = payload.Reason,
                Payload = new { reason = payload.Reason }
            }, ct);

        try
        {
            if (!running.Process.HasExited)
            {
                await Task.Delay(TimeSpan.FromSeconds(2), ct);
                if (!running.Process.HasExited)
                    running.Process.Kill(entireProcessTree: true);
            }
        }
        catch { /* best effort */ }
    }

    private async Task PumpHostPipeAsync(
        NamedPipeServerStream pipe,
        InteractiveExecutionStartPayload payload,
        string instanceId,
        string sessionToken,
        SessionRunnerPipeClient agentPipe,
        CancellationToken ct)
    {
        try
        {
            await pipe.WaitForConnectionAsync(ct);
            using var reader = new StreamReader(pipe, leaveOpen: true);
            while (!ct.IsCancellationRequested)
            {
                var line = await reader.ReadLineAsync(ct);
                if (line is null) break;
                await ForwardHostMessageAsync(line, payload, instanceId, sessionToken, agentPipe, ct);
            }
        }
        catch (OperationCanceledException) { }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Interactive host pipe failed for {ExecutionId}/{AttemptId}", payload.ExecutionId, payload.ExecutionAttemptId);
        }
    }

    private async Task ForwardHostMessageAsync(
        string raw,
        InteractiveExecutionStartPayload start,
        string instanceId,
        string sessionToken,
        SessionRunnerPipeClient agentPipe,
        CancellationToken ct)
    {
        using var document = JsonDocument.Parse(raw);
        var root = document.RootElement;
        var hostType = root.TryGetProperty("message_type", out var mt) ? mt.GetString() : null;
        var localType = hostType switch
        {
            "execution_host.ready" => LocalMessageTypes.InteractiveExecutionHeartbeat,
            "execution.started" => LocalMessageTypes.InteractiveExecutionStarted,
            "execution.log" => LocalMessageTypes.InteractiveExecutionLog,
            "execution.progress" => LocalMessageTypes.InteractiveExecutionProgress,
            "execution.metric" => LocalMessageTypes.InteractiveExecutionMetric,
            "execution.artifact" => LocalMessageTypes.InteractiveExecutionArtifact,
            "execution.result" => LocalMessageTypes.InteractiveExecutionCompleted,
            "execution.failed" => LocalMessageTypes.InteractiveExecutionFailed,
            "execution.cancelled" => LocalMessageTypes.InteractiveExecutionCancelled,
            "execution.heartbeat" => LocalMessageTypes.InteractiveExecutionHeartbeat,
            "automation.event" => LocalMessageTypes.InteractiveAutomationEvent,
            _ => LocalMessageTypes.InteractiveExecutionLog
        };

        object? payload = root.TryGetProperty("payload", out var p) ? p.Clone() : null;
        await agentPipe.SendInteractiveStatusAsync(instanceId, start.SessionId, sessionToken, localType,
            new InteractiveExecutionStatusPayload
            {
                ExecutionId = start.ExecutionId,
                ExecutionAttemptId = start.ExecutionAttemptId,
                Payload = payload,
                Message = hostType
            }, ct);
    }

    private async Task WatchProcessAsync(
        Process process,
        InteractiveExecutionStartPayload payload,
        string instanceId,
        string sessionToken,
        SessionRunnerPipeClient agentPipe,
        string key,
        CancellationToken ct)
    {
        try
        {
            await process.WaitForExitAsync(CancellationToken.None);
            var exitCode = process.ExitCode;
            var messageType = exitCode == 0
                ? LocalMessageTypes.InteractiveExecutionCompleted
                : LocalMessageTypes.InteractiveExecutionFailed;

            await agentPipe.SendInteractiveStatusAsync(instanceId, payload.SessionId, sessionToken, messageType,
                new InteractiveExecutionStatusPayload
                {
                    ExecutionId = payload.ExecutionId,
                    ExecutionAttemptId = payload.ExecutionAttemptId,
                    ProcessId = process.Id,
                    ExitCode = exitCode,
                    ErrorCode = exitCode == 0 ? null : "INTERACTIVE_HOST_EXIT_CODE",
                    Message = $"ExecutionHost exited with code {exitCode}",
                    Payload = new { exit_code = exitCode }
                }, CancellationToken.None);
        }
        catch (Exception ex)
        {
            await SendFailedAsync(payload, instanceId, sessionToken, agentPipe, "INTERACTIVE_HOST_FAILURE", ex.Message, CancellationToken.None);
        }
        finally
        {
            _running.TryRemove(key, out _);
            process.Dispose();
        }
    }

    private string ResolveExecutionHostPath(string resolvedPath)
    {
        var candidates = new[]
        {
            resolvedPath,
            _options.ExecutionHostPath,
            Path.Combine(AppContext.BaseDirectory, "ExecutionHost.exe"),
            Path.Combine(AppContext.BaseDirectory, "..", "AgentService", "ExecutionHost.exe")
        }.Where(p => !string.IsNullOrWhiteSpace(p)).Select(p => Path.GetFullPath(p!)).ToArray();

        foreach (var candidate in candidates)
        {
            if (Path.GetFileName(candidate).Equals("ExecutionHost.exe", StringComparison.OrdinalIgnoreCase) && File.Exists(candidate))
                return candidate;
        }

        throw new InvalidOperationException($"ExecutionHost.exe not found. Searched: {string.Join(", ", candidates)}");
    }

    private static async Task SendFailedAsync(
        InteractiveExecutionStartPayload payload,
        string instanceId,
        string sessionToken,
        SessionRunnerPipeClient agentPipe,
        string errorCode,
        string message,
        CancellationToken ct)
    {
        await agentPipe.SendInteractiveStatusAsync(instanceId, payload.SessionId, sessionToken, LocalMessageTypes.InteractiveExecutionFailed,
            new InteractiveExecutionStatusPayload
            {
                ExecutionId = payload.ExecutionId,
                ExecutionAttemptId = payload.ExecutionAttemptId,
                ErrorCode = errorCode,
                Message = message,
                Payload = new { error_code = errorCode, message }
            }, ct);
    }

    private static string Key(string executionId, string attemptId) => $"{executionId}|{attemptId}";
    private static int? SafePid(Process process)
    {
        try { return process.Id; }
        catch { return null; }
    }

    private static void TryKill(Process process)
    {
        try
        {
            if (!process.HasExited)
                process.Kill(entireProcessTree: true);
        }
        catch { /* best effort */ }
    }

    private sealed record RunningHost(Process Process, CancellationTokenSource Cancellation);
}
