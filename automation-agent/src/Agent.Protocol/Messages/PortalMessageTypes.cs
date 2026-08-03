namespace Biason.AutomationAgent.Protocol.Messages;

/// <summary>
/// Catálogo fechado dos tipos de mensagem do protocolo Portal ↔ Agent (seção 9).
/// Mensagens cujo tipo não estiver aqui são rejeitadas — nunca aceite tipos arbitrários.
/// </summary>
public static class PortalMessageTypes
{
    // === Agent ===
    public const string Register = "agent.register";
    public const string Registered = "agent.registered";
    public const string RegistrationFailed = "agent.registration_failed";
    public const string Heartbeat = "agent.heartbeat";
    public const string HeartbeatAck = "agent.heartbeat_ack";
    public const string Profile = "agent.profile";
    public const string Capacity = "agent.capacity";
    public const string StateChanged = "agent.state_changed";
    public const string Health = "agent.health";
    public const string DiagnosticsSummary = "agent.diagnostics_summary";
    public const string Draining = "agent.draining";
    public const string Ready = "agent.ready";

    // === Execução ===
    public const string ExecutionOffer = "execution.offer";
    public const string ExecutionAccept = "execution.accept";
    public const string ExecutionReject = "execution.reject";
    public const string ExecutionCommit = "execution.commit";
    public const string ExecutionCommitRejected = "execution.commit_rejected";
    public const string ExecutionPreparing = "execution.preparing";
    public const string ExecutionStarted = "execution.started";
    public const string ExecutionProgress = "execution.progress";
    public const string ExecutionLog = "execution.log";
    public const string ExecutionMetric = "execution.metric";
    public const string ExecutionArtifactCreated = "execution.artifact_created";
    public const string ExecutionCompleted = "execution.completed";
    public const string ExecutionFailed = "execution.failed";
    public const string ExecutionCancelRequested = "execution.cancel_requested";
    public const string ExecutionCancelling = "execution.cancelling";
    public const string ExecutionCancelled = "execution.cancelled";
    public const string ExecutionTimedOut = "execution.timed_out";
    public const string ExecutionInterrupted = "execution.interrupted";

    // === Lease ===
    public const string LeaseGranted = "execution.lease_granted";
    public const string LeaseRenew = "execution.lease_renew";
    public const string LeaseRenewed = "execution.lease_renewed";
    public const string LeaseExpired = "execution.lease_expired";
    public const string LeaseLost = "execution.lease_lost";

    // === Sincronização ===
    public const string SyncRequest = "agent.sync_request";
    public const string SyncState = "agent.sync_state";
    public const string MessageAck = "message.ack";
    public const string CommandAck = "command.ack";
    public const string ProtocolError = "protocol.error";

    /// <summary>Mensagens que o Agent envia ao Portal.</summary>
    public static readonly IReadOnlySet<string> Outbound = new HashSet<string>(StringComparer.Ordinal)
    {
        Register, Heartbeat, Profile, Capacity, StateChanged, Health, DiagnosticsSummary,
        Draining, Ready,
        ExecutionAccept, ExecutionReject, ExecutionPreparing, ExecutionStarted,
        ExecutionProgress, ExecutionLog, ExecutionMetric, ExecutionArtifactCreated,
        ExecutionCompleted, ExecutionFailed, ExecutionCancelling, ExecutionCancelled,
        ExecutionTimedOut, ExecutionInterrupted,
        LeaseRenew, LeaseLost,
        SyncState, MessageAck, CommandAck, ProtocolError
    };

    /// <summary>Mensagens que o Portal envia ao Agent. Base do Command Dispatcher.</summary>
    public static readonly IReadOnlySet<string> Inbound = new HashSet<string>(StringComparer.Ordinal)
    {
        Registered, RegistrationFailed, HeartbeatAck,
        ExecutionOffer, ExecutionCommit, ExecutionCommitRejected, ExecutionCancelRequested,
        LeaseGranted, LeaseRenewed, LeaseExpired,
        SyncRequest, MessageAck, CommandAck, ProtocolError
    };

    /// <summary>
    /// Comandos que disparam ação local e por isso exigem persistência na Inbox
    /// antes do processamento (seção 14).
    /// </summary>
    public static readonly IReadOnlySet<string> Commands = new HashSet<string>(StringComparer.Ordinal)
    {
        ExecutionOffer, ExecutionCommit, ExecutionCancelRequested, SyncRequest
    };

    public static bool IsKnown(string messageType) =>
        Inbound.Contains(messageType) || Outbound.Contains(messageType);

    public static bool IsCommand(string messageType) => Commands.Contains(messageType);
}
