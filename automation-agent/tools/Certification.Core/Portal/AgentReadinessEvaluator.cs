using System.Text.Json;

namespace Biason.AutomationAgent.Certification.Core.Portal;

public enum AgentReadinessState
{
    NotRegistered,
    Registered,
    Ready,
    Degraded,
    Stale
}

public sealed record AgentReadiness(
    AgentReadinessState State,
    string? AgentId,
    string? ConnectivityStatus,
    string? HealthStatus,
    DateTimeOffset? LastSeenAtUtc,
    bool HeartbeatRecent)
{
    /// <summary>
    /// True when the Agent counts as certification-ready: registered,
    /// connectivity "online", health "healthy" or "degraded" (both allowed
    /// per docs/certification-harness.md item 12), and a recent heartbeat.
    /// </summary>
    public bool IsReady => State is AgentReadinessState.Ready or AgentReadinessState.Degraded;
}

/// <summary>
/// Turns a raw GET /agents/{id} JSON payload (see
/// backend/modules/fleet/domain/agent.py for the real field names/values)
/// into an <see cref="AgentReadiness"/> verdict, without ever fabricating a
/// READY state the Portal itself did not report.
/// </summary>
public static class AgentReadinessEvaluator
{
    public static AgentReadiness Evaluate(JsonElement? agentJson, TimeSpan heartbeatFreshnessWindow, DateTimeOffset nowUtc)
    {
        if (agentJson is null)
            return new AgentReadiness(AgentReadinessState.NotRegistered, null, null, null, null, false);

        var element = agentJson.Value;
        var agentId = TryGetString(element, "id");
        var connectivity = TryGetString(element, "connectivity_status");
        var health = TryGetString(element, "health_status");
        var lastSeen = TryGetDateTimeOffset(element, "last_seen_at");

        var heartbeatRecent = lastSeen is not null && (nowUtc - lastSeen.Value) <= heartbeatFreshnessWindow;

        if (string.IsNullOrEmpty(connectivity) || connectivity == "offline" || connectivity == "disconnected")
            return new AgentReadiness(AgentReadinessState.Registered, agentId, connectivity, health, lastSeen, heartbeatRecent);

        if (connectivity == "stale")
            return new AgentReadiness(AgentReadinessState.Stale, agentId, connectivity, health, lastSeen, heartbeatRecent);

        if (connectivity is "online" or "connecting")
        {
            if (!heartbeatRecent)
                return new AgentReadiness(AgentReadinessState.Stale, agentId, connectivity, health, lastSeen, heartbeatRecent);

            var state = health == "healthy"
                ? AgentReadinessState.Ready
                : AgentReadinessState.Degraded;
            return new AgentReadiness(state, agentId, connectivity, health, lastSeen, heartbeatRecent);
        }

        return new AgentReadiness(AgentReadinessState.Registered, agentId, connectivity, health, lastSeen, heartbeatRecent);
    }

    private static string? TryGetString(JsonElement element, string property) =>
        element.TryGetProperty(property, out var value) && value.ValueKind == JsonValueKind.String
            ? value.GetString()
            : null;

    private static DateTimeOffset? TryGetDateTimeOffset(JsonElement element, string property) =>
        element.TryGetProperty(property, out var value) &&
        value.ValueKind == JsonValueKind.String &&
        DateTimeOffset.TryParse(value.GetString(), out var parsed)
            ? parsed
            : null;
}
