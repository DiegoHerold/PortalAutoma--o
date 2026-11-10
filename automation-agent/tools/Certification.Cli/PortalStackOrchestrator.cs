using Biason.AutomationAgent.Certification.Core.Processes;

namespace Biason.AutomationAgent.Certification.Cli;

/// <summary>
/// Reuses the Portal stack managed by scripts/portal.ps1
/// (docs/certification-harness.md item 16: harness deve reutilizar ambiente
/// já ativo). Never runs `portal.ps1 stop` — only `start` and `status`, so
/// the harness cannot destroy state the user is relying on outside
/// certification.
/// </summary>
public sealed class PortalStackOrchestrator
{
    private readonly string _repoRoot;

    public PortalStackOrchestrator(string repoRoot)
    {
        _repoRoot = repoRoot;
    }

    private Task<ShellResult> RunPortalScriptAsync(string command, TimeSpan timeout, CancellationToken ct) =>
        ShellRunner.RunAsync(
            "powershell.exe",
            $"-NoProfile -ExecutionPolicy Bypass -File \"{Path.Combine(_repoRoot, "scripts", "portal.ps1")}\" {command}",
            _repoRoot,
            timeout: timeout,
            ct: ct);

    public async Task<bool> IsStackRunningAsync(CancellationToken ct = default)
    {
        var result = await RunPortalScriptAsync("status", TimeSpan.FromSeconds(30), ct);
        return result.Success;
    }

    public async Task UpAsync(CancellationToken ct = default)
    {
        var result = await RunPortalScriptAsync("start", TimeSpan.FromMinutes(5), ct);
        if (!result.Success)
            throw new InvalidOperationException($"'portal.ps1 start' failed:\n{result.Stderr}\n{result.Stdout}");
    }
}
