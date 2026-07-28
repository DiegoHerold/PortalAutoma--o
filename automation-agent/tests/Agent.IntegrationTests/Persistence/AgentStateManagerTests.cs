using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.StateMachines;
using Biason.AutomationAgent.IntegrationTests.Helpers;
using FluentAssertions;
using Xunit;

namespace Biason.AutomationAgent.IntegrationTests.Persistence;

public class AgentStateManagerTests : IDisposable
{
    private readonly TestHelper _helper = new();

    [Fact]
    public async Task TransitionTo_ValidTransition_ChangesState()
    {
        await _helper.InitializeDatabaseAsync();
        var mgr = _helper.CreateStateManager();

        mgr.CurrentState.Should().Be(AgentState.Starting);

        await mgr.TransitionToAsync(AgentState.Initializing, "Test startup");
        mgr.CurrentState.Should().Be(AgentState.Initializing);
        mgr.PreviousState.Should().Be(AgentState.Starting);
    }

    [Fact]
    public async Task TransitionTo_InvalidTransition_Throws()
    {
        await _helper.InitializeDatabaseAsync();
        var mgr = _helper.CreateStateManager();

        var act = () => mgr.TransitionToAsync(AgentState.Ready, "Skip init");
        await act.Should().ThrowAsync<InvalidStateTransitionException>();
        mgr.CurrentState.Should().Be(AgentState.Starting);
    }

    [Fact]
    public async Task GetTransitionHistory_ReturnsRecords()
    {
        await _helper.InitializeDatabaseAsync();
        var mgr = _helper.CreateStateManager();

        await mgr.TransitionToAsync(AgentState.Initializing, "Init");
        await mgr.TransitionToAsync(AgentState.Ready, "Ready");

        var history = await mgr.GetTransitionHistoryAsync();
        history.Should().HaveCountGreaterOrEqualTo(2);
        history[0].ToState.Should().Be("Ready");
        history[1].ToState.Should().Be("Initializing");
    }

    [Fact]
    public async Task FullLifecycle_StartToStop()
    {
        await _helper.InitializeDatabaseAsync();
        var mgr = _helper.CreateStateManager();

        await mgr.TransitionToAsync(AgentState.Initializing, "Init");
        await mgr.TransitionToAsync(AgentState.Ready, "Ready");
        await mgr.TransitionToAsync(AgentState.Stopping, "Shutdown");
        await mgr.TransitionToAsync(AgentState.Stopped, "Stopped");

        mgr.CurrentState.Should().Be(AgentState.Stopped);
    }

    public void Dispose() => _helper.Dispose();
}
