namespace Biason.AutomationAgent.Protocol.Messages;

/// <summary>
/// Catalogo fechado dos tipos de mensagem do protocolo Portal-Agent.
/// Os nomes de wire seguem o gateway real do Portal e contracts/messages.
/// Alguns tipos internos legados continuam no conjunto Outbound porque o
/// Outbox os normaliza para mensagens de wire antes de persistir/enviar.
/// </summary>
public static class PortalMessageTypes
{
    // === Agent / gateway ===
    public const string Register = "agent.register";
    public const string Registered = "agent.registered";
    public const string RegistrationFailed = "agent.registration_failed";
    public const string Connected = "agent.connected";
    public const string Resumed = "agent.resumed";
    public const string Heartbeat = "agent.heartbeat";
    public const string HeartbeatAck = "agent.heartbeat_ack";
    public const string PortalAck = "portal.ack";
    public const string PortalError = "portal.error";
    public const string PortalDisconnect = "portal.disconnect";
    public const string Profile = "agent.profile.updated";
    public const string Capacity = "agent.capacity.updated";
    public const string CapabilitiesUpdated = "agent.capabilities.updated";
    public const string StateChanged = "agent.state_changed";
    public const string Health = "agent.health";
    public const string DiagnosticsSummary = "agent.diagnostics_summary";
    public const string DiagnosticResult = "agent.diagnostic.result";
    public const string Draining = "agent.draining";
    public const string Ready = "agent.ready";

    // === Execution ===
    public const string ExecutionOffer = "execution.offer";
    public const string ExecutionAccept = "execution.accepted";
    public const string ExecutionReject = "execution.rejected";
    public const string ExecutionCommit = "execution.commit";
    public const string ExecutionCommitRejected = "execution.commit_rejected";
    public const string ExecutionPreparing = "execution.preparing";
    public const string ExecutionStarted = "execution.started";
    public const string ExecutionProgress = "execution.progress";
    public const string ExecutionLog = "execution.log";
    public const string ExecutionMetric = "execution.metric";
    public const string ExecutionEventBatch = "execution.event.batch";
    /// <summary>Evento da automacao (contracts/automation-events/v1), transportado dentro do execution.event.batch.</summary>
    public const string AutomationEvent = "automation.event";
    public const string ExecutionArtifactCreated = "artifact.created";
    public const string ExecutionCompleted = "execution.completed";
    public const string ExecutionFailed = "execution.failed";
    public const string ExecutionCancelRequested = "execution.cancel";
    public const string ExecutionCancelling = "execution.cancelling";
    public const string ExecutionCancelled = "execution.cancelled";
    public const string ExecutionTimedOut = "execution.timed_out";
    public const string ExecutionInterrupted = "execution.interrupted";
    public const string ArtifactConfirmed = "artifact.confirmed";
    public const string ArtifactUploaded = "artifact.uploaded";
    public const string ArtifactFailed = "artifact.failed";

    // === Lease ===
    public const string LeaseGranted = "execution.lease_granted";
    public const string LeaseRenew = "execution.lease.renew";
    public const string LeaseRenewed = "execution.lease_renewed";
    public const string LeaseExpired = "execution.lease_expired";
    public const string LeaseLost = "execution.lease_lost";

    // === Sync / control ===
    public const string SyncRequest = "agent.sync_request";
    public const string SyncState = "agent.sync_state";
    public const string MessageAck = "message.ack";
    public const string CommandAck = "agent.command.ack";
    public const string ProtocolError = "protocol.error";

    /// <summary>Mensagens que o Agent pode publicar antes da normalizacao de wire.</summary>
    public static readonly IReadOnlySet<string> Outbound = new HashSet<string>(StringComparer.Ordinal)
    {
        Register, Connected, Resumed, Heartbeat, Profile, Capacity, CapabilitiesUpdated,
        DiagnosticResult, StateChanged, Health, DiagnosticsSummary, Draining, Ready,
        ExecutionAccept, ExecutionReject, ExecutionCommitRejected, ExecutionPreparing, ExecutionStarted,
        ExecutionProgress, ExecutionLog, ExecutionMetric, ExecutionEventBatch, AutomationEvent, ExecutionArtifactCreated,
        ExecutionCompleted, ExecutionFailed, ExecutionCancelling, ExecutionCancelled,
        ExecutionTimedOut, ExecutionInterrupted, ArtifactUploaded, ArtifactFailed,
        LeaseRenew, LeaseLost, SyncState, CommandAck, ProtocolError
    };

    /// <summary>Mensagens que o Portal envia ao Agent.</summary>
    public static readonly IReadOnlySet<string> Inbound = new HashSet<string>(StringComparer.Ordinal)
    {
        Registered, RegistrationFailed, Connected, Resumed, HeartbeatAck,
        PortalAck, PortalError, PortalDisconnect,
        ExecutionOffer, ExecutionCommit, ExecutionCommitRejected, ExecutionCancelRequested,
        LeaseGranted, LeaseRenewed, LeaseExpired,
        ArtifactConfirmed, SyncRequest, MessageAck, CommandAck, ProtocolError
    };

    /// <summary>Comandos que exigem persistencia na Inbox antes do processamento.</summary>
    public static readonly IReadOnlySet<string> Commands = new HashSet<string>(StringComparer.Ordinal)
    {
        ExecutionOffer, ExecutionCommit, ExecutionCancelRequested, SyncRequest, ArtifactConfirmed
    };

    public static bool IsKnown(string messageType) =>
        Inbound.Contains(messageType) || Outbound.Contains(messageType);

    public static bool IsCommand(string messageType) => Commands.Contains(messageType);
}
