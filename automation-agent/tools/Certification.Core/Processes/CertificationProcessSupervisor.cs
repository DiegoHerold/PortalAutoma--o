using System.Diagnostics;
using Microsoft.Extensions.Logging;

namespace Biason.AutomationAgent.Certification.Core.Processes;

/// <summary>
/// Starts, waits on, and stops a supervised process for the certification
/// harness (docs/certification-harness.md item 14). Responsible for PID
/// tracking (item 15), stdout/stderr capture, and clean shutdown with a
/// forced-kill fallback (item 13) — never leaves an orphaned process
/// behind, and always records whether a forced kill happened rather than
/// silently succeeding.
/// </summary>
public sealed class CertificationProcessSupervisor
{
    private readonly ILogger<CertificationProcessSupervisor> _logger;

    public CertificationProcessSupervisor(ILogger<CertificationProcessSupervisor> logger)
    {
        _logger = logger;
    }

    public ManagedProcessHandle Start(
        string name,
        string fileName,
        string arguments,
        string workingDirectory,
        IReadOnlyDictionary<string, string?> environment,
        string logDirectory,
        string pidDirectory)
    {
        Directory.CreateDirectory(logDirectory);
        Directory.CreateDirectory(pidDirectory);

        var stdoutPath = Path.Combine(logDirectory, $"{name}.stdout.log");
        var stderrPath = Path.Combine(logDirectory, $"{name}.stderr.log");
        var pidFilePath = Path.Combine(pidDirectory, $"{name}.pid");

        if (OperatingSystem.IsWindows())
        {
            try
            {
                var launched = NativeProcess.Start(fileName, arguments, workingDirectory, environment, stdoutPath, stderrPath);
                var handle = new ManagedProcessHandle
                {
                    Name = name,
                    ProcessId = launched.ProcessId,
                    StartedAtUtc = DateTime.UtcNow,
                    StdoutPath = stdoutPath,
                    StderrPath = stderrPath,
                    PidFilePath = pidFilePath,
                    SupportsGracefulStop = true,
                    NativeProcessHandle = launched.ProcessHandle
                };
                WritePidFile(handle);
                _logger.LogInformation("Started {Name} (PID {Pid}) with graceful-stop support.", name, handle.ProcessId);
                return handle;
            }
            catch (Exception ex)
            {
                _logger.LogWarning(
                    ex,
                    "Native process launch failed for {Name}; falling back to Process.Start without graceful-stop support.",
                    name);
            }
        }

        return StartFallback(name, fileName, arguments, workingDirectory, environment, stdoutPath, stderrPath, pidFilePath);
    }

    private ManagedProcessHandle StartFallback(
        string name,
        string fileName,
        string arguments,
        string workingDirectory,
        IReadOnlyDictionary<string, string?> environment,
        string stdoutPath,
        string stderrPath,
        string pidFilePath)
    {
        var startInfo = new ProcessStartInfo
        {
            FileName = fileName,
            Arguments = arguments,
            WorkingDirectory = workingDirectory,
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
        };
        foreach (var (key, value) in environment)
        {
            if (value is null)
                startInfo.Environment.Remove(key);
            else
                startInfo.Environment[key] = value;
        }

        var process = new Process { StartInfo = startInfo, EnableRaisingEvents = true };
        var stdoutWriter = new StreamWriter(stdoutPath, append: false) { AutoFlush = true };
        var stderrWriter = new StreamWriter(stderrPath, append: false) { AutoFlush = true };
        process.OutputDataReceived += (_, e) => { if (e.Data is not null) stdoutWriter.WriteLine(e.Data); };
        process.ErrorDataReceived += (_, e) => { if (e.Data is not null) stderrWriter.WriteLine(e.Data); };

        process.Start();
        process.BeginOutputReadLine();
        process.BeginErrorReadLine();

        var handle = new ManagedProcessHandle
        {
            Name = name,
            ProcessId = process.Id,
            StartedAtUtc = DateTime.UtcNow,
            StdoutPath = stdoutPath,
            StderrPath = stderrPath,
            PidFilePath = pidFilePath,
            SupportsGracefulStop = false
        };
        WritePidFile(handle);
        _logger.LogInformation(
            "Started {Name} (PID {Pid}) via Process.Start fallback (kill-only shutdown).", name, handle.ProcessId);
        return handle;
    }

    public bool IsRunning(ManagedProcessHandle handle)
    {
        try
        {
            using var process = Process.GetProcessById(handle.ProcessId);
            return !process.HasExited;
        }
        catch (ArgumentException)
        {
            return false;
        }
    }

    public async Task<StopResult> StopAsync(ManagedProcessHandle handle, TimeSpan gracefulTimeout, CancellationToken ct = default)
    {
        var stopwatch = Stopwatch.StartNew();
        var gracefulAttempted = false;

        if (!IsRunning(handle))
        {
            RemovePidFile(handle);
            return new StopResult(false, false, stopwatch.Elapsed, TryGetExitCode(handle));
        }

        if (handle.SupportsGracefulStop && OperatingSystem.IsWindows())
        {
            gracefulAttempted = NativeProcess.TrySendGracefulStop(handle.ProcessId);
            if (gracefulAttempted)
            {
                _logger.LogInformation("Sent CTRL_BREAK to {Name} (PID {Pid}); waiting up to {Timeout}s for graceful exit.",
                    handle.Name, handle.ProcessId, gracefulTimeout.TotalSeconds);
                await WaitForExitAsync(handle, gracefulTimeout, ct);
            }
        }

        var forced = false;
        if (IsRunning(handle))
        {
            forced = true;
            _logger.LogWarning("{Name} (PID {Pid}) did not exit within the graceful timeout; forcing termination.",
                handle.Name, handle.ProcessId);
            TryKill(handle);
            await WaitForExitAsync(handle, TimeSpan.FromSeconds(10), ct);
        }

        if (handle.NativeProcessHandle != 0 && OperatingSystem.IsWindows())
            NativeProcess.CloseProcessHandle((IntPtr)handle.NativeProcessHandle);

        RemovePidFile(handle);
        return new StopResult(gracefulAttempted, forced, stopwatch.Elapsed, TryGetExitCode(handle));
    }

    private async Task WaitForExitAsync(ManagedProcessHandle handle, TimeSpan timeout, CancellationToken ct)
    {
        using var cts = CancellationTokenSource.CreateLinkedTokenSource(ct);
        cts.CancelAfter(timeout);
        try
        {
            using var process = Process.GetProcessById(handle.ProcessId);
            await process.WaitForExitAsync(cts.Token);
        }
        catch (ArgumentException)
        {
            // Already exited.
        }
        catch (OperationCanceledException)
        {
            // Timed out waiting; caller checks IsRunning next.
        }
    }

    private void TryKill(ManagedProcessHandle handle)
    {
        try
        {
            using var process = Process.GetProcessById(handle.ProcessId);
            process.Kill(entireProcessTree: true);
        }
        catch (ArgumentException)
        {
            // Already exited.
        }
        catch (InvalidOperationException)
        {
            // Already exited between the check and the kill.
        }
    }

    private static int? TryGetExitCode(ManagedProcessHandle handle)
    {
        try
        {
            using var process = Process.GetProcessById(handle.ProcessId);
            return process.HasExited ? process.ExitCode : null;
        }
        catch (ArgumentException)
        {
            return null;
        }
        catch (InvalidOperationException)
        {
            return null;
        }
    }

    private static void WritePidFile(ManagedProcessHandle handle) =>
        File.WriteAllText(handle.PidFilePath, $"{handle.ProcessId}\n{handle.StartedAtUtc:O}\n");

    private static void RemovePidFile(ManagedProcessHandle handle)
    {
        try
        {
            if (File.Exists(handle.PidFilePath))
                File.Delete(handle.PidFilePath);
        }
        catch (IOException)
        {
            // Best-effort cleanup.
        }
    }

    /// <summary>
    /// Detects a stale PID file left behind by a harness process that died
    /// without cleaning up (docs/certification-harness.md item 58). Returns
    /// true (and best-effort kills the PID) if the file existed and pointed
    /// at a still-running or now-dead process; false if there was nothing
    /// to recover.
    /// </summary>
    public bool RecoverStalePidFile(string pidFilePath)
    {
        if (!File.Exists(pidFilePath))
            return false;

        var lines = File.ReadAllLines(pidFilePath);
        if (lines.Length == 0 || !int.TryParse(lines[0], out var pid))
        {
            File.Delete(pidFilePath);
            return true;
        }

        try
        {
            using var process = Process.GetProcessById(pid);
            if (!process.HasExited)
            {
                _logger.LogWarning("Recovering stale certification process PID {Pid} from a previous run; terminating it.", pid);
                process.Kill(entireProcessTree: true);
            }
        }
        catch (ArgumentException)
        {
            // Process no longer exists — nothing to kill, just clean the file.
        }

        File.Delete(pidFilePath);
        return true;
    }
}
