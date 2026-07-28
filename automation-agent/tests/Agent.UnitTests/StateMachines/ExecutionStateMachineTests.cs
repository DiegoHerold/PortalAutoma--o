using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.StateMachines;
using FluentAssertions;
using Xunit;

namespace Biason.AutomationAgent.UnitTests.StateMachines;

public class ExecutionStateMachineTests
{
    [Theory]
    [InlineData(ExecutionState.Offered, ExecutionState.Reserved, true)]
    [InlineData(ExecutionState.Offered, ExecutionState.Rejected, true)]
    [InlineData(ExecutionState.Reserved, ExecutionState.Committed, true)]
    [InlineData(ExecutionState.Committed, ExecutionState.Preparing, true)]
    [InlineData(ExecutionState.Preparing, ExecutionState.Starting, true)]
    [InlineData(ExecutionState.Starting, ExecutionState.Running, true)]
    [InlineData(ExecutionState.Running, ExecutionState.Succeeded, true)]
    [InlineData(ExecutionState.Running, ExecutionState.Failed, true)]
    [InlineData(ExecutionState.Running, ExecutionState.CancelRequested, true)]
    [InlineData(ExecutionState.Running, ExecutionState.TimedOut, true)]
    [InlineData(ExecutionState.CancelRequested, ExecutionState.Cancelling, true)]
    [InlineData(ExecutionState.Cancelling, ExecutionState.Cancelled, true)]
    [InlineData(ExecutionState.Interrupted, ExecutionState.Orphaned, true)]
    // Invalid transitions
    [InlineData(ExecutionState.Offered, ExecutionState.Running, false)]
    [InlineData(ExecutionState.Succeeded, ExecutionState.Running, false)]
    [InlineData(ExecutionState.Failed, ExecutionState.Running, false)]
    [InlineData(ExecutionState.Cancelled, ExecutionState.Running, false)]
    [InlineData(ExecutionState.Orphaned, ExecutionState.Running, false)]
    public void CanTransition_ReturnsExpected(ExecutionState from, ExecutionState to, bool expected)
    {
        ExecutionStateMachine.CanTransition(from, to).Should().Be(expected);
    }

    [Theory]
    [InlineData(ExecutionState.Succeeded, true)]
    [InlineData(ExecutionState.Rejected, true)]
    [InlineData(ExecutionState.Cancelled, true)]
    [InlineData(ExecutionState.Failed, true)]
    [InlineData(ExecutionState.TimedOut, true)]
    [InlineData(ExecutionState.Orphaned, true)]
    [InlineData(ExecutionState.Running, false)]
    [InlineData(ExecutionState.Offered, false)]
    [InlineData(ExecutionState.Preparing, false)]
    public void IsTerminal_ReturnsExpected(ExecutionState state, bool expected)
    {
        ExecutionStateMachine.IsTerminal(state).Should().Be(expected);
    }

    [Fact]
    public void ValidateTransition_InvalidTransition_Throws()
    {
        var act = () => ExecutionStateMachine.ValidateTransition(ExecutionState.Offered, ExecutionState.Running);
        act.Should().Throw<InvalidStateTransitionException>();
    }

    [Fact]
    public void TerminalStates_HaveNoTransitions()
    {
        var terminals = new[] { ExecutionState.Succeeded, ExecutionState.Rejected, ExecutionState.Cancelled, ExecutionState.Failed, ExecutionState.TimedOut };
        foreach (var state in terminals)
        {
            ExecutionStateMachine.GetAllowedTransitions(state).Should().BeEmpty($"{state} is terminal");
        }
    }
}
