using System.Text.Json;
using Biason.AutomationAgent.Certification.Core.Portal;
using FluentAssertions;
using Xunit;

namespace Biason.AutomationAgent.Certification.Tests;

public class AgentReadinessEvaluatorTests
{
    private static JsonElement Agent(string connectivity, string health, DateTimeOffset? lastSeen)
    {
        var json = JsonSerializer.Serialize(new
        {
            id = "agt_test",
            connectivity_status = connectivity,
            health_status = health,
            last_seen_at = lastSeen?.ToString("O")
        });
        return JsonDocument.Parse(json).RootElement;
    }

    [Fact]
    public void NullAgent_IsNotRegistered()
    {
        var result = AgentReadinessEvaluator.Evaluate(null, TimeSpan.FromSeconds(60), DateTimeOffset.UtcNow);
        result.State.Should().Be(AgentReadinessState.NotRegistered);
        result.IsReady.Should().BeFalse();
    }

    [Fact]
    public void OnlineHealthyWithRecentHeartbeat_IsReady()
    {
        var now = DateTimeOffset.UtcNow;
        var result = AgentReadinessEvaluator.Evaluate(Agent("online", "healthy", now.AddSeconds(-5)), TimeSpan.FromSeconds(60), now);
        result.State.Should().Be(AgentReadinessState.Ready);
        result.IsReady.Should().BeTrue();
    }

    [Fact]
    public void OnlineDegradedHealth_IsStillReady_PerItem12()
    {
        var now = DateTimeOffset.UtcNow;
        var result = AgentReadinessEvaluator.Evaluate(Agent("online", "degraded", now.AddSeconds(-5)), TimeSpan.FromSeconds(60), now);
        result.State.Should().Be(AgentReadinessState.Degraded);
        result.IsReady.Should().BeTrue();
    }

    [Fact]
    public void OnlineButStaleHeartbeat_IsNotReady()
    {
        var now = DateTimeOffset.UtcNow;
        var result = AgentReadinessEvaluator.Evaluate(Agent("online", "healthy", now.AddMinutes(-10)), TimeSpan.FromSeconds(60), now);
        result.HeartbeatRecent.Should().BeFalse();
        result.IsReady.Should().BeFalse();
    }

    [Fact]
    public void OfflineAgent_IsRegisteredButNotReady()
    {
        var now = DateTimeOffset.UtcNow;
        var result = AgentReadinessEvaluator.Evaluate(Agent("offline", "healthy", now.AddMinutes(-30)), TimeSpan.FromSeconds(60), now);
        result.State.Should().Be(AgentReadinessState.Registered);
        result.IsReady.Should().BeFalse();
    }

    [Fact]
    public void StaleConnectivity_IsReportedAsStale()
    {
        var now = DateTimeOffset.UtcNow;
        var result = AgentReadinessEvaluator.Evaluate(Agent("stale", "healthy", now.AddMinutes(-5)), TimeSpan.FromSeconds(60), now);
        result.State.Should().Be(AgentReadinessState.Stale);
        result.IsReady.Should().BeFalse();
    }
}
