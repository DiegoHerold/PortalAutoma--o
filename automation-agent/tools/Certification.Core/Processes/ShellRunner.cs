using System.Diagnostics;

namespace Biason.AutomationAgent.Certification.Core.Processes;

public sealed record ShellResult(int ExitCode, string Stdout, string Stderr)
{
    public bool Success => ExitCode == 0;
}

/// <summary>
/// Runs a one-shot command to completion and captures its output — for
/// short-lived orchestration steps (docker compose, the Python backend
/// certification CLI), not for the long-lived, gracefully-stoppable
/// Agent.Service process (see <see cref="CertificationProcessSupervisor"/>
/// for that).
/// </summary>
public static class ShellRunner
{
    public static async Task<ShellResult> RunAsync(
        string fileName,
        string arguments,
        string? workingDirectory = null,
        IReadOnlyDictionary<string, string?>? environment = null,
        TimeSpan? timeout = null,
        CancellationToken ct = default)
    {
        var startInfo = new ProcessStartInfo
        {
            FileName = fileName,
            Arguments = arguments,
            WorkingDirectory = workingDirectory ?? Environment.CurrentDirectory,
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
        };
        if (environment is not null)
        {
            foreach (var (key, value) in environment)
            {
                if (value is null) startInfo.Environment.Remove(key);
                else startInfo.Environment[key] = value;
            }
        }

        using var process = new Process { StartInfo = startInfo };
        process.Start();

        var stdoutTask = process.StandardOutput.ReadToEndAsync(ct);
        var stderrTask = process.StandardError.ReadToEndAsync(ct);

        using var cts = CancellationTokenSource.CreateLinkedTokenSource(ct);
        if (timeout is not null)
            cts.CancelAfter(timeout.Value);

        try
        {
            await process.WaitForExitAsync(cts.Token);
        }
        catch (OperationCanceledException)
        {
            try { process.Kill(entireProcessTree: true); } catch { /* best effort */ }
            throw new TimeoutException($"'{fileName} {arguments}' did not exit within {timeout}.");
        }

        var stdout = await stdoutTask;
        var stderr = await stderrTask;
        return new ShellResult(process.ExitCode, stdout, stderr);
    }
}
