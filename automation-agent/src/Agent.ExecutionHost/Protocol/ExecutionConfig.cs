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
