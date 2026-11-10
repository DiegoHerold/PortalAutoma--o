namespace Biason.AutomationAgent.Protocol.Local;

public static class LocalMessageTypes
{
    public const string Hello = "session_runner.hello";
    public const string Challenge = "session_runner.challenge";
    public const string Authenticate = "session_runner.authenticate";
    public const string Register = "session_runner.register";
    public const string Registered = "session_runner.registered";
    public const string Heartbeat = "session_runner.heartbeat";
    public const string HeartbeatAck = "session_runner.heartbeat_ack";
    public const string SessionStateChanged = "session.state_changed";
    public const string DesktopStateChanged = "desktop.state_changed";
    public const string Stopping = "session_runner.stopping";
    public const string ProtocolError = "protocol.error";

    public const string InteractiveExecutionStart = "interactive.execution.start";
    public const string InteractiveExecutionCancel = "interactive.execution.cancel";
    public const string InteractiveExecutionStarted = "interactive.execution.started";
    public const string InteractiveExecutionLog = "interactive.execution.log";
    public const string InteractiveExecutionProgress = "interactive.execution.progress";
    public const string InteractiveExecutionMetric = "interactive.execution.metric";
    public const string InteractiveExecutionArtifact = "interactive.execution.artifact";
    public const string InteractiveExecutionCompleted = "interactive.execution.completed";
    public const string InteractiveExecutionFailed = "interactive.execution.failed";
    public const string InteractiveExecutionCancelled = "interactive.execution.cancelled";
    public const string InteractiveExecutionHeartbeat = "interactive.execution.heartbeat";
    public const string InteractiveAutomationEvent = "interactive.automation.event";

    public static readonly IReadOnlySet<string> Known = new HashSet<string>(StringComparer.Ordinal)
    {
        Hello, Challenge, Authenticate, Register, Registered, Heartbeat, HeartbeatAck,
        SessionStateChanged, DesktopStateChanged, Stopping, ProtocolError,
        InteractiveExecutionStart, InteractiveExecutionCancel, InteractiveExecutionStarted,
        InteractiveExecutionLog, InteractiveExecutionProgress, InteractiveExecutionMetric,
        InteractiveExecutionArtifact, InteractiveExecutionCompleted, InteractiveExecutionFailed,
        InteractiveExecutionCancelled, InteractiveExecutionHeartbeat, InteractiveAutomationEvent
    };
}
