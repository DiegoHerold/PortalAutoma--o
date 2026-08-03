namespace Biason.AutomationAgent.Domain.Enums;

/// <summary>
/// Estado da conexão WebSocket com o Portal (seção 11).
///
/// Conceito distinto de <see cref="AgentState"/>: um Agent pode estar
/// <see cref="AgentState.Ready"/> (funcional localmente) enquanto a conexão está
/// <see cref="Reconnecting"/> ou <see cref="Disabled"/>. O heartbeat carrega os dois
/// campos lado a lado, nunca um substituindo o outro.
/// </summary>
public enum ConnectionState
{
    Disconnected,
    Connecting,
    Authenticating,
    Connected,
    Reconnecting,
    Degraded,
    Disabled
}
