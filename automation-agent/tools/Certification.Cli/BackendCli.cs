using System.Text.Json;
using Biason.AutomationAgent.Certification.Core.Processes;

namespace Biason.AutomationAgent.Certification.Cli;

/// <summary>
/// Shells out to `backend/.venv/Scripts/python -m
/// tools.certification.cli ...` — the Portal-side half of the harness
/// (backend/tools/certification/cli.py). Keeping the Portal HTTP contract
/// implemented once, in Python, next to the modules it calls, instead of
/// duplicating it in C#.
/// </summary>
public sealed class BackendCli
{
    private readonly string _repoRoot;

    public BackendCli(string repoRoot)
    {
        _repoRoot = repoRoot;
    }

    private async Task<JsonDocument> RunAsync(string subcommand, TimeSpan timeout, CancellationToken ct)
    {
        var result = await ShellRunner.RunAsync(
            Path.Combine(_repoRoot, "backend", ".venv", "Scripts", "python.exe"),
            $"-m tools.certification.cli {subcommand}",
            workingDirectory: Path.Combine(_repoRoot, "backend"),
            environment: new Dictionary<string, string?>
            {
                ["CERTIFICATION_PACKAGES_ROOT"] = Path.Combine(_repoRoot, "automation-agent", "certification"),
            },
            timeout: timeout,
            ct: ct);

        if (!result.Success && result.ExitCode != 3) // 3 == BLOCKED, still valid JSON on stdout
        {
            throw new InvalidOperationException(
                $"backend certification CLI '{subcommand}' failed (exit {result.ExitCode}):\n{result.Stderr}\n{result.Stdout}");
        }

        var trimmed = result.Stdout.Trim();
        if (trimmed.Length == 0)
            throw new InvalidOperationException($"backend certification CLI '{subcommand}' produced no output.\n{result.Stderr}");

        return JsonDocument.Parse(trimmed);
    }

    public async Task<JsonDocument> HealthAsync(CancellationToken ct = default) =>
        await RunAsync("health", TimeSpan.FromSeconds(20), ct);

    public async Task<JsonDocument> SeedAsync(CancellationToken ct = default) =>
        await RunAsync("seed", TimeSpan.FromMinutes(3), ct);

    public async Task<JsonDocument> CreateExecutionAsync(string scenario, string agentId, string runId, CancellationToken ct = default) =>
        await RunAsync($"create-execution --scenario {scenario} --agent-id {agentId} --run-id {runId}", TimeSpan.FromSeconds(30), ct);

    public async Task<JsonDocument> ObserveAsync(string executionId, CancellationToken ct = default) =>
        await RunAsync($"observe --execution-id {executionId}", TimeSpan.FromSeconds(30), ct);

    public async Task<JsonDocument> WaitForStatusAsync(string executionId, string status, int timeoutSeconds, CancellationToken ct = default) =>
        await RunAsync(
            $"wait-status --execution-id {executionId} --status {status} --timeout {timeoutSeconds}",
            TimeSpan.FromSeconds(timeoutSeconds + 30),
            ct);

    public async Task<JsonDocument> WaitAsync(string executionId, int timeoutSeconds, CancellationToken ct = default) =>
        await RunAsync(
            $"wait --execution-id {executionId} --timeout {timeoutSeconds}",
            TimeSpan.FromSeconds(timeoutSeconds + 30),
            ct);

    public async Task<JsonDocument> CancelAsync(string executionId, CancellationToken ct = default) =>
        await RunAsync($"cancel --execution-id {executionId}", TimeSpan.FromSeconds(30), ct);
}
