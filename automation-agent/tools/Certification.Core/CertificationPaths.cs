namespace Biason.AutomationAgent.Certification.Core;

/// <summary>
/// Layout for one certification run's own artifacts (docs/certification-harness.md
/// item 49). Distinct from the isolated Agent data directory
/// (<see cref="CertificationOptions.DataDirectory"/>), which
/// <c>AgentDirectoryResolver</c> populates on its own (config/database/store/
/// downloads/staging/executions/artifacts/spool/diagnostics/logs) once
/// Agent.Service starts with <c>AUTOMATION_AGENT_DATA_DIR</c> pointed at it.
/// </summary>
public sealed class CertificationPaths
{
    public string RunsRoot { get; }
    public string RunId { get; }
    public string RunRoot { get; }
    public string PortalLogsPath { get; }
    public string AgentLogsPath { get; }
    public string ExecutionsPath { get; }
    public string ReportPath { get; }
    public string PidDirectory { get; }

    public CertificationPaths(string repoRoot, string runId)
    {
        RunsRoot = Path.Combine(repoRoot, "automation-agent", "certification-runs");
        RunId = runId;
        RunRoot = Path.Combine(RunsRoot, runId);
        PortalLogsPath = Path.Combine(RunRoot, "portal");
        AgentLogsPath = Path.Combine(RunRoot, "agent");
        ExecutionsPath = Path.Combine(RunRoot, "executions");
        ReportPath = Path.Combine(RunRoot, "report.json");
        PidDirectory = Path.Combine(RunsRoot, "run");
    }

    public void EnsureDirectoriesExist()
    {
        Directory.CreateDirectory(RunRoot);
        Directory.CreateDirectory(PortalLogsPath);
        Directory.CreateDirectory(AgentLogsPath);
        Directory.CreateDirectory(ExecutionsPath);
        Directory.CreateDirectory(PidDirectory);
    }

    public static string NewRunId(DateTime utcNow, int sequence) =>
        $"cert_{utcNow:yyyyMMdd}_{sequence:000}";

    /// <summary>
    /// Picks the next unused sequence number for today so repeated
    /// `certification run` calls on the same day get cert_20260806_001,
    /// _002, etc. instead of colliding (docs/certification-harness.md item 48).
    /// </summary>
    public static string NextRunId(string repoRoot, DateTime utcNow)
    {
        var runsRoot = Path.Combine(repoRoot, "automation-agent", "certification-runs");
        var prefix = $"cert_{utcNow:yyyyMMdd}_";
        var sequence = 1;
        if (Directory.Exists(runsRoot))
        {
            var existing = Directory.GetDirectories(runsRoot, prefix + "*")
                .Select(Path.GetFileName)
                .Where(name => name is not null)
                .Select(name => name!)
                .ToList();
            while (existing.Contains(prefix + sequence.ToString("000")))
                sequence++;
        }

        return prefix + sequence.ToString("000");
    }
}
