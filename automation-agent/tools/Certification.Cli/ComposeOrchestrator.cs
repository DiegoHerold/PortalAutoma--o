using System.Text.Json;
using Biason.AutomationAgent.Certification.Core.Processes;

namespace Biason.AutomationAgent.Certification.Cli;

/// <summary>
/// Reuses the existing docker-compose.yml (docs/certification-harness.md
/// item 16: "Se Portal já roda em Docker Compose, harness deve reutilizar
/// ambiente já ativo"). Never runs `docker compose down` — only `up -d` and
/// `ps`, so the harness cannot destroy state the user is relying on outside
/// certification.
/// </summary>
public sealed class ComposeOrchestrator
{
    private readonly string _repoRoot;

    public ComposeOrchestrator(string repoRoot)
    {
        _repoRoot = repoRoot;
    }

    public async Task<bool> IsStackRunningAsync(CancellationToken ct = default)
    {
        var services = await PsAsync(ct);
        var required = new[] { "postgres", "redis", "minio", "backend" };
        return required.All(name => services.TryGetValue(name, out var state) &&
            (state is "running" or "healthy"));
    }

    public async Task UpAsync(CancellationToken ct = default)
    {
        var result = await ShellRunner.RunAsync("docker", "compose up -d", _repoRoot, timeout: TimeSpan.FromMinutes(5), ct: ct);
        if (!result.Success)
            throw new InvalidOperationException($"'docker compose up -d' failed:\n{result.Stderr}");
    }

    public async Task<Dictionary<string, string>> PsAsync(CancellationToken ct = default)
    {
        var result = await ShellRunner.RunAsync("docker", "compose ps --format json", _repoRoot, timeout: TimeSpan.FromSeconds(30), ct: ct);
        var states = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        if (!result.Success)
            return states;

        // `docker compose ps --format json` emits one JSON object per line
        // (compose v2) rather than a single JSON array.
        foreach (var line in result.Stdout.Split('\n', StringSplitOptions.RemoveEmptyEntries))
        {
            try
            {
                using var doc = JsonDocument.Parse(line);
                var root = doc.RootElement;
                var name = root.TryGetProperty("Service", out var svc) ? svc.GetString() : null;
                var health = root.TryGetProperty("Health", out var h) ? h.GetString() : null;
                var state = root.TryGetProperty("State", out var s) ? s.GetString() : null;
                if (name is null) continue;
                states[name] = !string.IsNullOrEmpty(health) ? health.ToLowerInvariant() : (state ?? "unknown").ToLowerInvariant();
            }
            catch (JsonException)
            {
                // Skip lines that are not valid JSON objects (older compose
                // versions or unexpected output); PsAsync degrades to
                // "unknown" for that service rather than throwing.
            }
        }
        return states;
    }
}
