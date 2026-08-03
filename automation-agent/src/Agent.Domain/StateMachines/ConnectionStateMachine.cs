using Biason.AutomationAgent.Domain.Enums;

namespace Biason.AutomationAgent.Domain.StateMachines;

/// <summary>
/// Transições válidas do estado da conexão WebSocket (seção 11).
/// Máquina de estados independente de <see cref="AgentStateMachine"/> e
/// <see cref="ExecutionStateMachine"/> — governa um conceito diferente.
/// </summary>
public sealed class ConnectionStateMachine
{
    private static readonly Dictionary<ConnectionState, HashSet<ConnectionState>> AllowedTransitions = new()
    {
        [ConnectionState.Disconnected] = new() { ConnectionState.Connecting, ConnectionState.Disabled },
        [ConnectionState.Connecting] = new() { ConnectionState.Authenticating, ConnectionState.Disconnected, ConnectionState.Reconnecting, ConnectionState.Disabled },
        [ConnectionState.Authenticating] = new() { ConnectionState.Connected, ConnectionState.Disconnected, ConnectionState.Reconnecting, ConnectionState.Disabled },
        [ConnectionState.Connected] = new() { ConnectionState.Degraded, ConnectionState.Reconnecting, ConnectionState.Disconnected, ConnectionState.Disabled },
        [ConnectionState.Degraded] = new() { ConnectionState.Connected, ConnectionState.Reconnecting, ConnectionState.Disconnected, ConnectionState.Disabled },
        [ConnectionState.Reconnecting] = new() { ConnectionState.Connecting, ConnectionState.Disconnected, ConnectionState.Disabled },
        [ConnectionState.Disabled] = new() { ConnectionState.Disconnected }
    };

    public static bool CanTransition(ConnectionState from, ConnectionState to)
    {
        return AllowedTransitions.TryGetValue(from, out var targets) && targets.Contains(to);
    }

    public static void ValidateTransition(ConnectionState from, ConnectionState to)
    {
        if (!CanTransition(from, to))
            throw new InvalidStateTransitionException(from.ToString(), to.ToString());
    }

    public static IReadOnlySet<ConnectionState> GetAllowedTransitions(ConnectionState from)
    {
        return AllowedTransitions.TryGetValue(from, out var targets) ? targets : new HashSet<ConnectionState>();
    }

    /// <summary>True para estados em que o Agent pode enviar mensagens pelo socket.</summary>
    public static bool IsOperational(ConnectionState state) =>
        state is ConnectionState.Connected or ConnectionState.Degraded;
}
