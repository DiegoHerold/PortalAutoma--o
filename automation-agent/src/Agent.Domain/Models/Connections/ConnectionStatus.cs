using Biason.AutomationAgent.Domain.Enums;

namespace Biason.AutomationAgent.Domain.Models.Connections;

/// <summary>Snapshot do estado atual da conexão com o Portal.</summary>
public sealed class ConnectionStatus
{
    public string ConnectionId { get; init; } = default!;
    public ConnectionState State { get; init; }
    public string Endpoint { get; init; } = default!;
    public DateTime? ConnectedAtUtc { get; init; }
    public DateTime? DisconnectedAtUtc { get; init; }
    public DateTime? LastMessageAtUtc { get; init; }
    public DateTime? LastPongAtUtc { get; init; }
    public string? DisconnectReason { get; init; }
    public int ReconnectAttempt { get; init; }
}

/// <summary>Evento de transição de estado da conexão, persistido em <c>connection_events</c>.</summary>
public sealed class ConnectionEvent
{
    public string? ConnectionId { get; init; }
    public ConnectionState? FromState { get; init; }
    public ConnectionState ToState { get; init; }
    public string? Reason { get; init; }
    public string? Detail { get; init; }
    public DateTime OccurredAtUtc { get; init; }
}
