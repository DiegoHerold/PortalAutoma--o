using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text.Json;
using Biason.AutomationAgent.ExecutionHost.Launchers;
using Biason.AutomationAgent.ExecutionHost.Protocol;
using Serilog;
using Serilog.Formatting.Compact;

// === ExecutionHost ===
// Separate process that runs automations in isolation.
// Receives config via temporary file, communicates with Agent Service via Named Pipe.
// Never accesses the main SQLite database or Portal directly.

var exitCode = 1;
PipeClient? pipeClient = null;
Process? automationProcess = null;

try
{
    // Parse command line: --config <path> --pipe <name> --entrypoint-type <type>
    var configPath = GetArg(args, "--config");
    var pipeName = GetArg(args, "--pipe") ?? Environment.GetEnvironmentVariable("AUTOMATION_PIPE_NAME");
    var entrypointType = GetArg(args, "--entrypoint-type");

    // Load execution config
    ExecutionConfig config;
    if (configPath is not null && File.Exists(configPath))
    {
        var json = await File.ReadAllTextAsync(configPath);
        config = JsonSerializer.Deserialize<ExecutionConfig>(json, new JsonSerializerOptions
        {
            PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower
        }) ?? throw new InvalidOperationException("Failed to parse execution config");

        // Delete config file immediately after reading (contains potential secrets)
        try { File.Delete(configPath); } catch { /* best effort */ }
    }
    else
    {
        // Fallback: build config from environment variables
        var executionId = Environment.GetEnvironmentVariable("AUTOMATION_EXECUTION_ID")
            ?? throw new InvalidOperationException("Missing AUTOMATION_EXECUTION_ID");
        var attemptId = Environment.GetEnvironmentVariable("AUTOMATION_ATTEMPT_ID")
            ?? throw new InvalidOperationException("Missing AUTOMATION_ATTEMPT_ID");
        var workspace = Environment.GetEnvironmentVariable("AUTOMATION_WORKSPACE")
            ?? throw new InvalidOperationException("Missing AUTOMATION_WORKSPACE");
        var packagePath = Environment.GetEnvironmentVariable("AUTOMATION_PACKAGE_PATH")
            ?? throw new InvalidOperationException("Missing AUTOMATION_PACKAGE_PATH");
        var runtimePath = Environment.GetEnvironmentVariable("AUTOMATION_RUNTIME_PATH")
            ?? throw new InvalidOperationException("Missing AUTOMATION_RUNTIME_PATH");
        var timeout = int.TryParse(Environment.GetEnvironmentVariable("AUTOMATION_TIMEOUT_SECONDS"), out var t) ? t : 3600;

        // "??=" não aceita throw expression como lado direito (CS8115); if explícito.
        if (pipeName is null)
            throw new InvalidOperationException("Missing pipe name");

        config = new ExecutionConfig
        {
            ExecutionId = executionId,
            AttemptId = attemptId,
            PipeName = pipeName,
            Token = Guid.NewGuid().ToString("N"),
            TimeoutSeconds = timeout,
            Entrypoint = new EntrypointConfig { Type = entrypointType ?? "python_function" },
            Paths = new PathsConfig
            {
                RuntimePath = runtimePath,
                PackagePath = packagePath,
                WorkspacePath = workspace,
                InputPath = Path.Combine(workspace, "input"),
                OutputPath = Path.Combine(workspace, "output"),
                ArtifactsPath = Path.Combine(workspace, "artifacts"),
                TempPath = Path.Combine(workspace, "temp"),
                LogsPath = Path.Combine(workspace, "logs")
            }
        };
    }

    // Initialize logging to workspace
    var logPath = Path.Combine(config.Paths.LogsPath, "execution-host-.log");
    Log.Logger = new LoggerConfiguration()
        .MinimumLevel.Information()
        .Enrich.WithProperty("ExecutionId", config.ExecutionId)
        .Enrich.WithProperty("AttemptId", config.AttemptId)
        .WriteTo.File(
            new CompactJsonFormatter(),
            logPath,
            rollingInterval: RollingInterval.Infinite,
            fileSizeLimitBytes: 50 * 1024 * 1024)
        .CreateLogger();

    Log.Information("ExecutionHost starting for {ExecutionId}/{AttemptId}", config.ExecutionId, config.AttemptId);
    if (string.Equals(config.Mode, "interactive", StringComparison.OrdinalIgnoreCase))
    {
        ConfigureInteractiveDpi();
        Log.Information("ExecutionHost interactive context: session={SessionId}, dpi={Dpi}, monitors={Monitors}, resolution={Width}x{Height}",
            config.InteractiveContext?.SessionId,
            config.InteractiveContext?.DpiScale,
            config.InteractiveContext?.MonitorCount,
            config.InteractiveContext?.DesktopResolution?.Width,
            config.InteractiveContext?.DesktopResolution?.Height);
    }

    // Validate paths
    ValidatePaths(config.Paths);

    // Connect to Agent Service via Named Pipe
    pipeClient = new PipeClient(config.PipeName, config.ExecutionId, config.AttemptId);
    try
    {
        await pipeClient.ConnectAsync(timeoutMs: 10000);
        await pipeClient.SendAsync(MessageTypes.HostReady, new { pid = Environment.ProcessId });
        Log.Information("Connected to Agent Service pipe: {PipeName}", config.PipeName);
    }
    catch (Exception ex)
    {
        Log.Warning(ex, "Could not connect to Agent pipe, continuing without pipe communication");
        await pipeClient.DisposeAsync();
        pipeClient = null;
    }

    // Set up cancellation with timeout
    using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(config.TimeoutSeconds));
    var ct = cts.Token;

    // Build and launch the automation process
    var startInfo = RuntimeLauncher.BuildStartInfo(config);

    if (pipeClient is not null)
        await pipeClient.SendAsync(MessageTypes.Started, new
        {
            entrypoint_type = config.Entrypoint.Type,
            executable = startInfo.FileName,
            pid = Environment.ProcessId
        }, ct);

    automationProcess = new Process { StartInfo = startInfo };

    // Capture stdout and stderr asynchronously
    var stdoutPath = Path.Combine(config.Paths.LogsPath, "stdout.log");
    var stderrPath = Path.Combine(config.Paths.LogsPath, "stderr.log");

    automationProcess.Start();
    Log.Information("Automation process started: PID={Pid}, Executable={Exe}",
        automationProcess.Id, startInfo.FileName);

    if (pipeClient is not null)
        await pipeClient.SendMetricAsync("automation_pid", automationProcess.Id, ct);

    // Stream stdout and stderr to files and pipe
    var stdoutTask = CaptureOutputAsync(automationProcess.StandardOutput, stdoutPath, "stdout", pipeClient, ct);
    var stderrTask = CaptureOutputAsync(automationProcess.StandardError, stderrPath, "stderr", pipeClient, ct);

    // Monitor process and collect metrics
    var metricsTask = CollectMetricsAsync(automationProcess, config.Paths.OutputPath, pipeClient, ct);

    // Wait for process to exit or cancellation
    try
    {
        await automationProcess.WaitForExitAsync(ct);
    }
    catch (OperationCanceledException)
    {
        Log.Warning("Execution timed out or cancelled, terminating automation process");

        if (pipeClient is not null)
            await pipeClient.SendAsync(MessageTypes.CancellationRequested, null, CancellationToken.None);

        // Graceful shutdown attempt
        if (!automationProcess.HasExited)
        {
            try
            {
                automationProcess.Kill(entireProcessTree: true);
                automationProcess.WaitForExit(config.GracefulShutdownSeconds * 1000);
            }
            catch { /* process may have exited already */ }
        }

        if (pipeClient is not null)
            await pipeClient.SendAsync(MessageTypes.Cancelled, null, CancellationToken.None);
    }

    // Wait for output capture to complete
    await Task.WhenAll(stdoutTask, stderrTask);

    // Cancel the metrics task
    exitCode = automationProcess.HasExited ? automationProcess.ExitCode : -1;

    Log.Information("Automation process exited with code {ExitCode}", exitCode);

    // Send result
    if (pipeClient is not null)
    {
        var resultPayload = new
        {
            exit_code = exitCode,
            success = exitCode == 0,
            output_path = config.Paths.OutputPath,
            artifacts_path = config.Paths.ArtifactsPath
        };

        await pipeClient.SendAsync(
            exitCode == 0 ? MessageTypes.Result : MessageTypes.Failed,
            resultPayload,
            CancellationToken.None);
    }
}
catch (Exception ex)
{
    Log.Fatal(ex, "ExecutionHost fatal error");

    if (pipeClient is not null)
    {
        try
        {
            await pipeClient.SendAsync(MessageTypes.Failed, new
            {
                error = ex.GetType().Name,
                // Redact: only include message, not full stack trace
                message = ex.Message
            }, CancellationToken.None);
        }
        catch { /* pipe may be disconnected */ }
    }

    exitCode = 2;
}
finally
{
    if (automationProcess is not null)
    {
        if (!automationProcess.HasExited)
        {
            try { automationProcess.Kill(entireProcessTree: true); } catch { }
        }
        automationProcess.Dispose();
    }

    if (pipeClient is not null)
        await pipeClient.DisposeAsync();

    Log.Information("ExecutionHost exiting with code {ExitCode}", exitCode);
    await Log.CloseAndFlushAsync();
}

return exitCode;

// === Helper functions ===

static string? GetArg(string[] args, string name)
{
    for (int i = 0; i < args.Length - 1; i++)
    {
        if (args[i].Equals(name, StringComparison.OrdinalIgnoreCase))
            return args[i + 1];
    }
    return null;
}

static void ValidatePaths(PathsConfig paths)
{
    var required = new (string Name, string Path)[]
    {
        ("RuntimePath", paths.RuntimePath),
        ("PackagePath", paths.PackagePath),
        ("WorkspacePath", paths.WorkspacePath),
    };

    foreach (var (name, path) in required)
    {
        if (string.IsNullOrWhiteSpace(path))
            throw new InvalidOperationException($"Missing required path: {name}");
        if (!Directory.Exists(path))
            throw new InvalidOperationException($"Path does not exist: {name}={path}");
    }

    // Ensure output directories exist
    Directory.CreateDirectory(paths.InputPath);
    Directory.CreateDirectory(paths.OutputPath);
    Directory.CreateDirectory(paths.ArtifactsPath);
    Directory.CreateDirectory(paths.TempPath);
    Directory.CreateDirectory(paths.LogsPath);
}

static async Task CaptureOutputAsync(
    StreamReader reader, string filePath, string streamName,
    PipeClient? pipe, CancellationToken ct)
{
    try
    {
        await using var writer = new StreamWriter(filePath, append: false) { AutoFlush = true };
        string? line;
        while ((line = await reader.ReadLineAsync(ct)) is not null)
        {
            await writer.WriteLineAsync(line);

            if (pipe is not null && pipe.IsConnected)
            {
                try
                {
                    await pipe.SendLogAsync(streamName == "stderr" ? "error" : "info", line, ct);
                }
                catch { /* pipe failure should not stop capture */ }
            }
        }
    }
    catch (OperationCanceledException) { /* expected on cancellation */ }
    catch (Exception ex)
    {
        Log.Warning(ex, "Error capturing {StreamName}", streamName);
    }
}

static async Task CollectMetricsAsync(
    Process process, string outputPath, PipeClient? pipe, CancellationToken ct)
{
    var startTime = DateTime.UtcNow;
    long peakMemoryMb = 0;
    double cpuTimeSeconds = 0;
    int peakProcessCount = 0;

    try
    {
        while (!process.HasExited && !ct.IsCancellationRequested)
        {
            try
            {
                process.Refresh();
                var memMb = process.WorkingSet64 / (1024 * 1024);
                if (memMb > peakMemoryMb) peakMemoryMb = memMb;

                cpuTimeSeconds = process.TotalProcessorTime.TotalSeconds;

                if (pipe is not null && pipe.IsConnected)
                {
                    await pipe.SendMetricAsync("memory_mb", memMb, ct);
                    await pipe.SendMetricAsync("cpu_time_seconds", cpuTimeSeconds, ct);
                }
            }
            catch (InvalidOperationException) { break; } // process exited

            await Task.Delay(2000, ct);
        }
    }
    catch (OperationCanceledException) { }
    catch (Exception ex)
    {
        Log.Warning(ex, "Error collecting metrics");
    }

    // Write final metrics
    var durationMs = (long)(DateTime.UtcNow - startTime).TotalMilliseconds;
    var metrics = new
    {
        duration_ms = durationMs,
        peak_memory_mb = peakMemoryMb,
        cpu_time_seconds = Math.Round(cpuTimeSeconds, 2),
        peak_process_count = peakProcessCount
    };

    try
    {
        var metricsJson = JsonSerializer.Serialize(metrics, new JsonSerializerOptions { WriteIndented = true });
        var metricsPath = Path.Combine(outputPath, "metrics.json");
        await File.WriteAllTextAsync(metricsPath, metricsJson, CancellationToken.None);
    }
    catch (Exception ex)
    {
        Log.Warning(ex, "Error writing metrics file");
    }
}

static void ConfigureInteractiveDpi()
{
    if (!OperatingSystem.IsWindows())
        return;

    try
    {
        // Per-monitor awareness where supported; fallback to system DPI aware.
        if (!SetProcessDpiAwarenessContext(new IntPtr(-4)))
            SetProcessDPIAware();
    }
    catch
    {
        try { SetProcessDPIAware(); } catch { }
    }
}

[DllImport("user32.dll")]
static extern bool SetProcessDPIAware();

[DllImport("user32.dll")]
static extern bool SetProcessDpiAwarenessContext(IntPtr dpiContext);
