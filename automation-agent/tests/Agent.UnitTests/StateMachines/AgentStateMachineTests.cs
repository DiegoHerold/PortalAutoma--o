using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.StateMachines;
using FluentAssertions;
using Xunit;

namespace Biason.AutomationAgent.UnitTests.StateMachines;

public class AgentStateMachineTests
{
    [Theory]
    [InlineData(AgentState.Starting, AgentState.Initializing, true)]
    [InlineData(AgentState.Starting, AgentState.Faulted, true)]
    [InlineData(AgentState.Initializing, AgentState.Ready, true)]
    [InlineData(AgentState.Initializing, AgentState.Degraded, true)]
    [InlineData(AgentState.Initializing, AgentState.Faulted, true)]
    [InlineData(AgentState.Ready, AgentState.Degraded, true)]
    [InlineData(AgentState.Ready, AgentState.Stopping, true)]
    [InlineData(AgentState.Ready, AgentState.Draining, true)]
    [InlineData(AgentState.Ready, AgentState.Updating, true)]
    [InlineData(AgentState.Degraded, AgentState.Ready, true)]
    [InlineData(AgentState.Degraded, AgentState.Stopping, true)]
    [InlineData(AgentState.Stopping, AgentState.Stopped, true)]
    [InlineData(AgentState.Faulted, AgentState.Starting, true)]
    // Invalid transitions
    [InlineData(AgentState.Starting, AgentState.Ready, false)]
    [InlineData(AgentState.Starting, AgentState.Stopping, false)]
    [InlineData(AgentState.Stopped, AgentState.Ready, false)]
    [InlineData(AgentState.Stopped, AgentState.Starting, false)]
    [InlineData(AgentState.Ready, AgentState.Initializing, false)]
    [InlineData(AgentState.Ready, AgentState.Starting, false)]
    public void CanTransition_ReturnsExpected(AgentState from, AgentState to, bool expected)
    {
        AgentStateMachine.CanTransition(from, to).Should().Be(expected);
    }

    [Fact]
    public void ValidateTransition_ValidTransition_DoesNotThrow()
    {
        var act = () => AgentStateMachine.ValidateTransition(AgentState.Starting, AgentState.Initializing);
        act.Should().NotThrow();
    }

    [Fact]
    public void ValidateTransition_InvalidTransition_Throws()
    {
        var act = () => AgentStateMachine.ValidateTransition(AgentState.Starting, AgentState.Ready);
        act.Should().Throw<InvalidStateTransitionException>()
            .Which.FromState.Should().Be("Starting");
    }

    [Fact]
    public void GetAllowedTransitions_ReturnsCorrectSet()
    {
        var allowed = AgentStateMachine.GetAllowedTransitions(AgentState.Ready);
        allowed.Should().Contain(AgentState.Degraded);
        allowed.Should().Contain(AgentState.Stopping);
        allowed.Should().NotContain(AgentState.Starting);
    }

    [Fact]
    public void Stopped_HasNoTransitions()
    {
        var allowed = AgentStateMachine.GetAllowedTransitions(AgentState.Stopped);
        allowed.Should().BeEmpty();
    }

    [Fact]
    public void AllStates_HaveTransitionRules()
    {
        foreach (var state in Enum.GetValues<AgentState>())
        {
            // Should not throw — every state should have an entry
            var act = () => AgentStateMachine.GetAllowedTransitions(state);
            act.Should().NotThrow();
        }
    }
}
