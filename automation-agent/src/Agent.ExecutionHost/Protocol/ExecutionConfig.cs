using System.Text.Json.Serialization;

namespace Biason.AutomationAgent.ExecutionHost.Protocol;

/// <summary>
/// Configuration received by ExecutionHost to run an automation.
/// Loaded from a temporary config file (not from command line, to avoid secret leakage).
/// </summary>
public sealed class ExecutionConfig
{
    [JsonPropertyName("execution_id")]
    public string ExecutionId { get; init; } = default!;

    [JsonPropertyName("attempt_id")]
    public string AttemptId { get; init; } = default!;

    [JsonPropertyName("automation_id")]
    public string AutomationId { get; init; } = default!;

    [JsonPropertyName("mode")]
    public string Mode { get; init; } = "background";

    [JsonPropertyName("pipe_name")]
    public string PipeName { get; init; } = default!;

    [JsonPropertyName("token")]
    public string Token { get; init; } = default!;

    [JsonPropertyName("entrypoint")]
    public EntrypointConfig Entrypoint { get; init; } = default!;

    [JsonPropertyName("paths")]
    public PathsConfig Paths { get; init; } = default!;

    [JsonPropertyName("timeout_seconds")]
    public int TimeoutSeconds { get; init; } = 3600;

    [JsonPropertyName("graceful_shutdown_seconds")]
    public int GracefulShutdownSeconds { get; init; } = 30;

    [JsonPropertyName("environment")]
    public Dictionary<string, string>? Environment { get; init; }

    [JsonPropertyName("interactive_context")]
    public InteractiveContextConfig? InteractiveContext { get; init; }
}

public sealed class EntrypointConfig
{
    [JsonPropertyName("type")]
    public string Type { get; init; } = default!;

    [JsonPropertyName("executable_path")]
    public string? ExecutablePath { get; init; }

    [JsonPropertyName("arguments")]
    public string? Arguments { get; init; }

    [JsonPropertyName("module")]
    public string? Module { get; init; }

    [JsonPropertyName("callable")]
    public string? Callable { get; init; }

    [JsonPropertyName("script")]
    public string? Script { get; init; }
}

public sealed class PathsConfig
{
    [JsonPropertyName("runtime_path")]
    public string RuntimePath { get; init; } = default!;

    [JsonPropertyName("package_path")]
    public string PackagePath { get; init; } = default!;

    [JsonPropertyName("workspace_path")]
    public string WorkspacePath { get; init; } = default!;

    [JsonPropertyName("input_path")]
    public string InputPath { get; init; } = default!;

    [JsonPropertyName("output_path")]
    public string OutputPath { get; init; } = default!;

    [JsonPropertyName("artifacts_path")]
    public string ArtifactsPath { get; init; } = default!;

    [JsonPropertyName("temp_path")]
    public string TempPath { get; init; } = default!;

    [JsonPropertyName("logs_path")]
    public string LogsPath { get; init; } = default!;
}

public sealed class InteractiveContextConfig
{
    [JsonPropertyName("session_id")]
    public int SessionId { get; init; }

    [JsonPropertyName("session_type")]
    public string? SessionType { get; init; }

    [JsonPropertyName("desktop_resolution")]
    public DesktopResolutionConfig? DesktopResolution { get; init; }

    [JsonPropertyName("dpi_scale")]
    public double? DpiScale { get; init; }

    [JsonPropertyName("monitor_count")]
    public int? MonitorCount { get; init; }

    [JsonPropertyName("session_runner_instance_id")]
    public string? SessionRunnerInstanceId { get; init; }

    [JsonPropertyName("desktop_locked")]
    public bool DesktopLocked { get; init; }
}

public sealed class DesktopResolutionConfig
{
    [JsonPropertyName("width")]
    public int Width { get; init; }

    [JsonPropertyName("height")]
    public int Height { get; init; }
}
