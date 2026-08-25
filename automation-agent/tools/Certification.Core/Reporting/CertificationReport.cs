using System.Text.Json;
using System.Text.Json.Serialization;

namespace Biason.AutomationAgent.Certification.Core.Reporting;

/// <summary>Never PASS, only one of these four (docs/certification-harness.md item 51).</summary>
public enum ScenarioStatus
{
    Pass,
    Fail,
    Blocked,
    NotApplicable
}

/// <summary>Distinguishes a package tested through the local Agent pipeline
/// from one certified through the full Portal E2E path (item 54).</summary>
public enum CertificationMode
{
    LocalAgentTest,
    PortalE2E
}

public sealed class ComponentStatus
{
    public bool Healthy { get; set; }
    public string? Detail { get; set; }
}

public sealed class AgentStatus
{
    public bool Registered { get; set; }
    public bool Connected { get; set; }
    public bool Ready { get; set; }
    public string? AgentId { get; set; }
    public string? ConnectivityStatus { get; set; }
    public string? HealthStatus { get; set; }
    public DateTimeOffset? LastSeenAtUtc { get; set; }

    /// <summary>
    /// True for a real Agent.Service process supervised by this harness;
    /// false for any synthetic WebSocket client used elsewhere for gateway
    /// smoke tests (docs/certification-harness.md item 64 — never conflate
    /// the two in a report).
    /// </summary>
    public bool IsRealAgentService { get; set; } = true;
}

public sealed class ScenarioResult
{
    public required string ScenarioId { get; init; }
    public required CertificationMode Mode { get; init; }
    public required ScenarioStatus Status { get; set; }
    public string? ExecutionId { get; set; }
    public string? PortalStatus { get; set; }
    public string? Notes { get; set; }
    public TimeSpan? Duration { get; set; }
}

public sealed class CertificationReport
{
    public required string RunId { get; init; }
    public required DateTimeOffset StartedAtUtc { get; init; }
    public DateTimeOffset? FinishedAtUtc { get; set; }

    public ComponentStatus Portal { get; set; } = new();
    public ComponentStatus Storage { get; set; } = new();
    public ComponentStatus Gateway { get; set; } = new();
    public ComponentStatus Runtime { get; set; } = new();
    public AgentStatus Agent { get; set; } = new();

    public bool AgentServiceStartupPass { get; set; }
    public bool GracefulShutdownPass { get; set; }
    public bool ForcedTerminationOccurred { get; set; }

    public List<ScenarioResult> Scenarios { get; } = new();

    public List<string> Limitations { get; } = new();

    public string OverallGate =>
        Scenarios.Count == 0
            ? "BLOCKED"
            : Scenarios.All(s => s.Status == ScenarioStatus.Pass) ? "PASS"
            : Scenarios.Any(s => s.Status == ScenarioStatus.Fail) ? "FAIL"
            : "BLOCKED";

    private static readonly JsonSerializerOptions SerializerOptions = new()
    {
        WriteIndented = true,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
        Converters = { new JsonStringEnumConverter() }
    };

    public void Save(string path)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path) ?? ".");
        // Defense in depth against item 78 ("nunca gravar no report:
        // bearer token; secret; ..."): scan the serialized JSON for common
        // secret-shaped substrings before writing. This does not replace
        // discipline in what gets assigned to report fields in the first
        // place — it is a last-resort guard.
        var json = JsonSerializer.Serialize(this, SerializerOptions);
        SecretScan.ThrowIfLooksLikeSecret(json);
        File.WriteAllText(path, json);
    }
}
