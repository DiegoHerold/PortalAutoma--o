using System.Diagnostics;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Models.Execution;
using Microsoft.Extensions.Logging;

namespace Biason.AutomationAgent.Windows.Process;

public sealed class ProcessTreeManager : IProcessManager
{
    private readonly JobObjectManager _jobManager;
    private readonly IDirectoryResolver _dirs;
    private readonly ILogger<ProcessTreeManager> _logger;

    public ProcessTreeManager(
        JobObjectManager jobManager,
        IDirectoryResolver dirs,
        ILogger<ProcessTreeManager> logger)
    {
        _jobManager = jobManager;
        _dirs = dirs;
        _logger = logger;
    }

    public Task<ProcessHandle> LaunchAsync(ExecutionContext context, CancellationToken ct = default)
    {
        var jobName = $"exec_{context.ExecutionId}_{context.AttemptId}";
        var pipeName = $"biason_agent_{context.ExecutionId}_{context.AttemptId}";

        // Create Job Object with memory limit if specified
        long? memLimitMb = context.Manifest.Resources?.MaxMemoryMb;
        var jobHandle = _jobManager.CreateJobObject(jobName, memLimitMb, maxProcesses: 50);

        // Build ExecutionHost arguments
        var executionHostPath = Path.Combine(AppContext.BaseDirectory, "ExecutionHost.exe");
        if (!File.Exists(executionHostPath))
        {
            // Fallback for development: look in adjacent directory
            executionHostPath = Path.Combine(AppContext.BaseDirectory, "..", "Agent.ExecutionHost", "ExecutionHost.exe");
        }

        var args = BuildHostArguments(context, pipeName);

        var startInfo = new ProcessStartInfo
        {
            FileName = executionHostPath,
            Arguments = args,
            WorkingDirectory = context.WorkspacePath,
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
        };

        // Set environment variables (excluding secrets from command line)
        foreach (var (key, value) in context.EnvironmentVariables)
        {
            startInfo.Environment[key] = value;
        }

        startInfo.Environment["AUTOMATION_EXECUTION_ID"] = context.ExecutionId;
        startInfo.Environment["AUTOMATION_ATTEMPT_ID"] = context.AttemptId;
        startInfo.Environment["AUTOMATION_PIPE_NAME"] = pipeName;
        startInfo.Environment["AUTOMATION_WORKSPACE"] = context.WorkspacePath;
        startInfo.Environment["AUTOMATION_PACKAGE_PATH"] = context.PackagePath;
        startInfo.Environment["AUTOMATION_RUNTIME_PATH"] = context.RuntimePath;
        startInfo.Environment["AUTOMATION_TIMEOUT_SECONDS"] = context.TimeoutSeconds.ToString();

        var process = new System.Diagnostics.Process { StartInfo = startInfo };

        try
        {
            process.Start();
        }
        catch (Exception ex)
        {
            _jobManager.CloseJobObject(jobName);
            throw new InvalidOperationException($"Failed to start ExecutionHost: {ex.Message}", ex);
        }

        // Assign to Job Object
        if (!_jobManager.AssignProcess(jobHandle, process))
        {
            _logger.LogWarning("Failed to assign PID {Pid} to Job Object, process may survive agent crash", process.Id);
        }

        _logger.LogInformation("Launched ExecutionHost PID={Pid} for execution {ExecutionId}, pipe={PipeName}",
            process.Id, context.ExecutionId, pipeName);

        var handle = new ProcessHandle
        {
            ProcessId = process.Id,
            JobObjectHandle = jobHandle,
            PipeName = pipeName,
            Process = process
        };

        return Task.FromResult(handle);
    }

    public async Task TerminateAsync(ProcessHandle handle, int gracefulTimeoutMs, CancellationToken ct = default)
    {
        try
        {
            if (handle.Process.HasExited) return;

            // Try graceful shutdown via cancellation pipe message first
            // (The ExecutionHost monitors a named pipe for cancellation)
            _logger.LogInformation("Requesting graceful shutdown for PID {Pid}", handle.ProcessId);

            var exited = handle.Process.WaitForExit(gracefulTimeoutMs);
            if (!exited)
            {
                _logger.LogWarning("PID {Pid} did not exit gracefully, terminating via Job Object", handle.ProcessId);
                var jobName = $"exec_{handle.PipeName.Replace("biason_agent_", "")}";
                _jobManager.TerminateJobObject(jobName);

                // Give it a moment to actually terminate
                handle.Process.WaitForExit(3000);
            }
        }
        catch (InvalidOperationException)
        {
            // Process already exited
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error terminating PID {Pid}", handle.ProcessId);
        }
    }

    public bool IsRunning(ProcessHandle handle)
    {
        try { return !handle.Process.HasExited; }
        catch { return false; }
    }

    private static string BuildHostArguments(ExecutionContext context, string pipeName)
    {
        // ExecutionHost receives all config via environment variables (no secrets on command line)
        var entrypoint = context.Manifest.Entrypoint;
        return $"--pipe \"{pipeName}\" --entrypoint-type \"{entrypoint.Type}\"";
    }
}
