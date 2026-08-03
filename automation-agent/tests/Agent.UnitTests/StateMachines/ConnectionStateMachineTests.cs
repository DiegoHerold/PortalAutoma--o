using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.StateMachines;
using FluentAssertions;
using Xunit;

namespace Biason.AutomationAgent.UnitTests.StateMachines;

public class ConnectionStateMachineTests
{
    [Theory]
    [InlineData(ConnectionState.Disconnected, ConnectionState.Connecting, true)]
    [InlineData(ConnectionState.Disconnected, ConnectionState.Disabled, true)]
    [InlineData(ConnectionState.Connecting, ConnectionState.Authenticating, true)]
    [InlineData(ConnectionState.Authenticating, ConnectionState.Connected, true)]
    [InlineData(ConnectionState.Connected, ConnectionState.Reconnecting, true)]
    [InlineData(ConnectionState.Connected, ConnectionState.Degraded, true)]
    [InlineData(ConnectionState.Degraded, ConnectionState.Connected, true)]
    [InlineData(ConnectionState.Reconnecting, ConnectionState.Connecting, true)]
    [InlineData(ConnectionState.Disabled, ConnectionState.Disconnected, true)]
    // Inválidas — a mais importante: "reconectando" só faz sentido depois de ter
    // conectado ao menos uma vez, nunca direto do estado inicial.
    [InlineData(ConnectionState.Disconnected, ConnectionState.Reconnecting, false)]
    [InlineData(ConnectionState.Disconnected, ConnectionState.Connected, false)]
    [InlineData(ConnectionState.Disabled, ConnectionState.Connecting, false)]
    [InlineData(ConnectionState.Connecting, ConnectionState.Connected, false)]
    public void CanTransition_ReturnsExpected(ConnectionState from, ConnectionState to, bool expected)
    {
        ConnectionStateMachine.CanTransition(from, to).Should().Be(expected);
    }

    [Fact]
    public void ValidateTransition_InvalidTransition_Throws()
    {
        var act = () => ConnectionStateMachine.ValidateTransition(ConnectionState.Disconnected, ConnectionState.Reconnecting);
        act.Should().Throw<InvalidStateTransitionException>()
            .Which.FromState.Should().Be("Disconnected");
    }

    [Fact]
    public void ValidateTransition_ValidTransition_DoesNotThrow()
    {
        var act = () => ConnectionStateMachine.ValidateTransition(ConnectionState.Disconnected, ConnectionState.Connecting);
        act.Should().NotThrow();
    }

    [Theory]
    [InlineData(ConnectionState.Connected, true)]
    [InlineData(ConnectionState.Degraded, true)]
    [InlineData(ConnectionState.Disconnected, false)]
    [InlineData(ConnectionState.Connecting, false)]
    [InlineData(ConnectionState.Authenticating, false)]
    [InlineData(ConnectionState.Reconnecting, false)]
    [InlineData(ConnectionState.Disabled, false)]
    public void IsOperational_ReturnsExpected(ConnectionState state, bool expected)
    {
        ConnectionStateMachine.IsOperational(state).Should().Be(expected);
    }

    [Fact]
    public void Disabled_IsReachable_FromEveryOtherState()
    {
        // Desabilitar deve sempre ser possível, não importa em que ponto do ciclo de
        // vida a conexão está — é a válvula de escape do operador.
        foreach (ConnectionState state in Enum.GetValues<ConnectionState>())
        {
            if (state == ConnectionState.Disabled) continue;
            ConnectionStateMachine.CanTransition(state, ConnectionState.Disabled).Should().BeTrue($"{state} deve poder ir para Disabled");
        }
    }

    [Fact]
    public void GetAllowedTransitions_FromDisconnected_ExcludesReconnecting()
    {
        var allowed = ConnectionStateMachine.GetAllowedTransitions(ConnectionState.Disconnected);
        allowed.Should().Contain(ConnectionState.Connecting);
        allowed.Should().NotContain(ConnectionState.Reconnecting);
    }
}
