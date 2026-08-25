using System.Text.Json;
using Biason.AutomationAgent.Certification.Core.Portal;
using Biason.AutomationAgent.Certification.Core.Processes;

namespace Biason.AutomationAgent.Certification.Core.Diagnostics;

/// <summary>
/// Automatic diagnostic export when the Agent does not reach READY
/// (docs/certification-harness.md item 62): health probes, connection
/// state, identity, and the tail of the Agent's own stdout/stderr capture.
/// Written under the run's agent log directory so it is preserved with the
/// rest of the run's evidence (item 57).
/// </summary>
public static class DiagnosticDump
{
    public static async Task<string> WriteAsync(
        string outputDirectory,
        ProbeResult portalHealth,
        ProbeResult gatewayHealth,
        AgentReadiness? agentReadiness,
        ManagedProcessHandle? agentProcess,
        CancellationToken ct = default)
    {
        Directory.CreateDirectory(outputDirectory);
        var path = Path.Combine(outputDirectory, "diagnostic-dump.json");

        var payload = new
        {
            generated_at_utc = DateTimeOffset.UtcNow,
            portal_health = new { portalHealth.Healthy, portalHealth.Detail },
            gateway_health = new { gatewayHealth.Healthy, gatewayHealth.Detail },
            agent_readiness = agentReadiness is null
                ? null
                : new
                {
                    state = agentReadiness.State.ToString(),
                    agentReadiness.AgentId,
                    agentReadiness.ConnectivityStatus,
                    agentReadiness.HealthStatus,
                    agentReadiness.LastSeenAtUtc,
                    agentReadiness.HeartbeatRecent
                },
            agent_process = agentProcess is null
                ? null
                : new
                {
                    agentProcess.ProcessId,
                    agentProcess.StartedAtUtc,
                    agentProcess.SupportsGracefulStop,
                    stdout_tail = await TailAsync(agentProcess.StdoutPath, ct),
                    stderr_tail = await TailAsync(agentProcess.StderrPath, ct)
                }
        };

        var json = JsonSerializer.Serialize(payload, new JsonSerializerOptions { WriteIndented = true });
        await File.WriteAllTextAsync(path, json, ct);
        return path;
    }

    private static async Task<string[]> TailAsync(string path, CancellationToken ct, int maxLines = 200)
    {
        if (!File.Exists(path))
            return Array.Empty<string>();

        var lines = await File.ReadAllLinesAsync(path, ct);
        return lines.Length <= maxLines ? lines : lines[^maxLines..];
    }
}
