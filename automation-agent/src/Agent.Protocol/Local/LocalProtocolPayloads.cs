using System.Text.Json.Serialization;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Sessions;

namespace Biason.AutomationAgent.Protocol.Local;

public sealed class SessionRunnerHelloPayload
{
    [JsonPropertyName("instance_id")]
    public string InstanceId { get; init; } = default!;

    [JsonPropertyName("session_id")]
    public int SessionId { get; init; }

    [JsonPropertyName("process_id")]
    public int ProcessId { get; init; }

    [JsonPropertyName("version")]
    public string Version { get; init; } = default!;
}

public sealed class SessionRunnerChallengePayload
{
    [JsonPropertyName("challenge_id")]
    public string ChallengeId { get; init; } = default!;

    [JsonPropertyName("nonce")]
    public string Nonce { get; init; } = default!;

    [JsonPropertyName("expires_at_utc")]
    public DateTime ExpiresAtUtc { get; init; }
}

public sealed class SessionRunnerAuthenticatePayload
{
    [JsonPropertyName("challenge_id")]
    public string ChallengeId { get; init; } = default!;

    [JsonPropertyName("response")]
    public string Response { get; init; } = default!;
}

public sealed class SessionRunnerRegisterPayload
{
    [JsonPropertyName("instance_id")]
    public string InstanceId { get; init; } = default!;

    [JsonPropertyName("session_id")]
    public int SessionId { get; init; }

    [JsonPropertyName("process_id")]
    public int ProcessId { get; init; }

    [JsonPropertyName("version")]
    public string Version { get; init; } = default!;

    [JsonPropertyName("user")]
    public string? User { get; init; }

    [JsonPropertyName("domain")]
    public string? Domain { get; init; }

    [JsonPropertyName("session_type")]
    public SessionType SessionType { get; init; } = SessionType.Unknown;

    [JsonPropertyName("session_state")]
    public WindowsSessionState SessionState { get; init; } = WindowsSessionState.Unknown;

    [JsonPropertyName("desktop")]
    public DesktopState Desktop { get; init; } = DesktopState.Unknown;
}

public sealed class SessionRunnerRegisteredPayload
{
    [JsonPropertyName("session_token")]
    public string SessionToken { get; init; } = default!;

    [JsonPropertyName("expires_at_utc")]
    public DateTime ExpiresAtUtc { get; init; }

    [JsonPropertyName("heartbeat_interval_seconds")]
    public int HeartbeatIntervalSeconds { get; init; }
}

public sealed class SessionRunnerHeartbeatPayload
{
    [JsonPropertyName("session_id")]
    public int SessionId { get; init; }

    [JsonPropertyName("process_id")]
    public int ProcessId { get; init; }

    [JsonPropertyName("session_state")]
    public WindowsSessionState SessionState { get; init; } = WindowsSessionState.Unknown;

    [JsonPropertyName("desktop")]
    public DesktopState Desktop { get; init; } = DesktopState.Unknown;
}

public sealed class SessionStateChangedPayload
{
    [JsonPropertyName("session_id")]
    public int SessionId { get; init; }

    [JsonPropertyName("state")]
    public WindowsSessionState State { get; init; }

    [JsonPropertyName("event_type")]
    public string EventType { get; init; } = default!;

    [JsonPropertyName("desktop")]
    public DesktopState? Desktop { get; init; }
}

public sealed class LocalProtocolErrorPayload
{
    [JsonPropertyName("error_code")]
    public string ErrorCode { get; init; } = default!;

    [JsonPropertyName("error_message")]
    public string ErrorMessage { get; init; } = default!;
}

public sealed class InteractiveExecutionStartPayload
{
    [JsonPropertyName("execution_id")]
    public string ExecutionId { get; init; } = default!;

    [JsonPropertyName("execution_attempt_id")]
    public string ExecutionAttemptId { get; init; } = default!;

    [JsonPropertyName("session_id")]
    public int SessionId { get; init; }

    [JsonPropertyName("execution_token")]
    public string ExecutionToken { get; init; } = default!;

    [JsonPropertyName("execution_host")]
    public LocalExecutionHostReference ExecutionHost { get; init; } = default!;

    [JsonPropertyName("runtime_reference")]
    public LocalRuntimeReference RuntimeReference { get; init; } = default!;

    [JsonPropertyName("package_reference")]
    public LocalPackageReference PackageReference { get; init; } = default!;

    [JsonPropertyName("workspace_reference")]
    public string WorkspaceReference { get; init; } = default!;

    [JsonPropertyName("workspace_path")]
    public string WorkspacePath { get; init; } = default!;

    [JsonPropertyName("host_pipe_name")]
    public string HostPipeName { get; init; } = default!;

    [JsonPropertyName("execution_host_config_json")]
    public string ExecutionHostConfigJson { get; init; } = default!;

    [JsonPropertyName("interactive_context")]
    public object? InteractiveContext { get; init; }
}

public sealed class InteractiveExecutionCancelPayload
{
    [JsonPropertyName("execution_id")]
    public string ExecutionId { get; init; } = default!;

    [JsonPropertyName("execution_attempt_id")]
    public string ExecutionAttemptId { get; init; } = default!;

    [JsonPropertyName("reason")]
    public string Reason { get; init; } = default!;
}

public sealed class LocalExecutionHostReference
{
    [JsonPropertyName("executable")]
    public string Executable { get; init; } = "ExecutionHost.exe";

    [JsonPropertyName("resolved_path")]
    public string ResolvedPath { get; init; } = default!;
}

public sealed class LocalRuntimeReference
{
    [JsonPropertyName("id")]
    public string Id { get; init; } = default!;

    [JsonPropertyName("version")]
    public string Version { get; init; } = default!;

    [JsonPropertyName("resolved_path")]
    public string ResolvedPath { get; init; } = default!;
}

public sealed class LocalPackageReference
{
    [JsonPropertyName("automation_id")]
    public string AutomationId { get; init; } = default!;

    [JsonPropertyName("version")]
    public string Version { get; init; } = default!;

    [JsonPropertyName("resolved_path")]
    public string ResolvedPath { get; init; } = default!;
}

public sealed class InteractiveExecutionStatusPayload
{
    [JsonPropertyName("execution_id")]
    public string ExecutionId { get; init; } = default!;

    [JsonPropertyName("execution_attempt_id")]
    public string ExecutionAttemptId { get; init; } = default!;

    [JsonPropertyName("process_id")]
    public int? ProcessId { get; init; }

    [JsonPropertyName("exit_code")]
    public int? ExitCode { get; init; }

    [JsonPropertyName("error_code")]
    public string? ErrorCode { get; init; }

    [JsonPropertyName("message")]
    public string? Message { get; init; }

    [JsonPropertyName("payload")]
    public object? Payload { get; init; }
}
