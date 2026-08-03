using System.Diagnostics;
using System.Runtime.InteropServices;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Models.Interactive;
using DiagnosticsProcess = System.Diagnostics.Process;

namespace Biason.AutomationAgent.Windows.Process;

public sealed class WindowsApplicationProcessInspector : IApplicationProcessInspector
{
    public Task<IReadOnlyList<ApplicationProcessCandidate>> FindExistingAsync(string applicationKey, int sessionId, CancellationToken ct = default)
    {
        var names = ProcessNames(applicationKey);
        var candidates = new List<ApplicationProcessCandidate>();

        foreach (var name in names)
        {
            foreach (var process in DiagnosticsProcess.GetProcessesByName(name))
            {
                ct.ThrowIfCancellationRequested();
                using (process)
                {
                    var pid = SafePid(process);
                    if (pid is null)
                        continue;

                    var actualSession = TryGetSessionId(pid.Value);
                    if (actualSession is not null && actualSession.Value != sessionId)
                        continue;

                    candidates.Add(new ApplicationProcessCandidate
                    {
                        ApplicationKey = applicationKey,
                        ProcessId = pid.Value,
                        SessionId = actualSession,
                        ProcessPath = TryGetPath(process),
                        StartedAtUtc = TryGetStartTime(process),
                        WindowTitle = TryGetWindowTitle(process)
                    });
                }
            }
        }

        return Task.FromResult<IReadOnlyList<ApplicationProcessCandidate>>(candidates);
    }

    private static IReadOnlyList<string> ProcessNames(string applicationKey) =>
        applicationKey.ToLowerInvariant() switch
        {
            "office.excel" or "excel_application" => new[] { "EXCEL" },
            "dominio.installed" or "dominio_application" => new[] { "Dominio", "Domino", "Contabil" },
            _ => Array.Empty<string>()
        };

    private static int? SafePid(DiagnosticsProcess process)
    {
        try { return process.Id; }
        catch { return null; }
    }

    private static string? TryGetPath(DiagnosticsProcess process)
    {
        try { return process.MainModule?.FileName; }
        catch { return null; }
    }

    private static DateTime? TryGetStartTime(DiagnosticsProcess process)
    {
        try { return process.StartTime.ToUniversalTime(); }
        catch { return null; }
    }

    private static string? TryGetWindowTitle(DiagnosticsProcess process)
    {
        try { return string.IsNullOrWhiteSpace(process.MainWindowTitle) ? null : process.MainWindowTitle; }
        catch { return null; }
    }

    private static int? TryGetSessionId(int processId)
    {
        if (!OperatingSystem.IsWindows())
            return null;

        try
        {
            return ProcessIdToSessionId((uint)processId, out var sessionId) ? unchecked((int)sessionId) : null;
        }
        catch
        {
            return null;
        }
    }

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool ProcessIdToSessionId(uint dwProcessId, out uint pSessionId);
}
