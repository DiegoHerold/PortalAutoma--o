using Biason.AutomationAgent.Certification.Core.Processes;
using FluentAssertions;
using Microsoft.Extensions.Logging.Abstractions;
using Xunit;

namespace Biason.AutomationAgent.Certification.Tests;

/// <summary>
/// These tests spawn real child processes, so they only exercise the
/// Windows-specific graceful-stop path
/// (CertificationProcessSupervisor -> NativeProcess) when run on Windows —
/// the actual target platform for Agent.Service. On non-Windows CI they
/// still exercise the Process.Start fallback path. See
/// docs/certification-harness.md, "Testar restart do Harness" /
/// "Bounded Agent.Service runner" for what to re-verify on the real
/// machine (this is the part of the harness that could not be compiled or
/// run inside the research sandbox this suite was authored in).
/// </summary>
public class CertificationProcessSupervisorTests : IDisposable
{
    private readonly string _tempRoot = Path.Combine(Path.GetTempPath(), $"cert-supervisor-{Guid.NewGuid():N}");
    private readonly CertificationProcessSupervisor _supervisor = new(NullLogger<CertificationProcessSupervisor>.Instance);

    public CertificationProcessSupervisorTests() => Directory.CreateDirectory(_tempRoot);

    public void Dispose()
    {
        if (Directory.Exists(_tempRoot))
            Directory.Delete(_tempRoot, recursive: true);
    }

    private static (string fileName, string arguments) LongRunningCommand() =>
        OperatingSystem.IsWindows()
            ? ("cmd.exe", "/c \"ping -n 30 127.0.0.1 >nul\"")
            : ("/bin/sh", "-c \"sleep 30\"");

    private static (string fileName, string arguments) QuickExitCommand(int exitCode) =>
        OperatingSystem.IsWindows()
            ? ("cmd.exe", $"/c \"exit {exitCode}\"")
            : ("/bin/sh", $"-c \"exit {exitCode}\"");

    [Fact]
    public async Task Start_ThenStop_LeavesNoRunningProcess()
    {
        var (fileName, arguments) = LongRunningCommand();
        var handle = _supervisor.Start("test-long", fileName, arguments, _tempRoot,
            new Dictionary<string, string?>(), _tempRoot, _tempRoot);

        _supervisor.IsRunning(handle).Should().BeTrue();

        var result = await _supervisor.StopAsync(handle, TimeSpan.FromSeconds(5));

        _supervisor.IsRunning(handle).Should().BeFalse();
        File.Exists(handle.PidFilePath).Should().BeFalse("Stop must remove the PID file (item 15/58)");
    }

    [Fact]
    public void Start_ProcessThatExitsQuickly_IsNotRunningAfterExit()
    {
        var (fileName, arguments) = QuickExitCommand(0);
        var handle = _supervisor.Start("test-quick", fileName, arguments, _tempRoot,
            new Dictionary<string, string?>(), _tempRoot, _tempRoot);

        // Give the OS a brief moment to record the exit.
        var deadline = DateTime.UtcNow.AddSeconds(5);
        while (_supervisor.IsRunning(handle) && DateTime.UtcNow < deadline)
            Thread.Sleep(50);

        _supervisor.IsRunning(handle).Should().BeFalse();
    }

    [Fact]
    public async Task StopAsync_OnAlreadyExitedProcess_DoesNotThrow_AndReportsNoForcedTermination()
    {
        var (fileName, arguments) = QuickExitCommand(0);
        var handle = _supervisor.Start("test-crash", fileName, arguments, _tempRoot,
            new Dictionary<string, string?>(), _tempRoot, _tempRoot);

        var deadline = DateTime.UtcNow.AddSeconds(5);
        while (_supervisor.IsRunning(handle) && DateTime.UtcNow < deadline)
            Thread.Sleep(50);

        var result = await _supervisor.StopAsync(handle, TimeSpan.FromSeconds(5));
        result.ForcedTermination.Should().BeFalse();
    }

    [Fact]
    public async Task StopAsync_ProcessIgnoringGracefulStop_IsForceKilledWithinTimeout()
    {
        // A process with no console-ctrl handler of its own will not react
        // to CTRL_BREAK, so this exercises the forced-kill fallback (item 13).
        var (fileName, arguments) = LongRunningCommand();
        var handle = _supervisor.Start("test-forced", fileName, arguments, _tempRoot,
            new Dictionary<string, string?>(), _tempRoot, _tempRoot);

        var result = await _supervisor.StopAsync(handle, TimeSpan.FromSeconds(2));

        _supervisor.IsRunning(handle).Should().BeFalse();
        // cmd.exe/ping do not install a CTRL_BREAK handler, so the graceful
        // path is expected to fall through to a forced kill here — this
        // asserts the *fallback* works, not that graceful stop itself
        // succeeded (Agent.Service's own graceful-stop reaction is a
        // Generic-Host behavior that can only be verified against a real
        // build, see the class-level remarks).
        result.ForcedTermination.Should().BeTrue();
    }

    [Fact]
    public void RecoverStalePidFile_KillsProcessAndRemovesFile()
    {
        var (fileName, arguments) = LongRunningCommand();
        var handle = _supervisor.Start("test-stale", fileName, arguments, _tempRoot,
            new Dictionary<string, string?>(), _tempRoot, _tempRoot);
        File.Exists(handle.PidFilePath).Should().BeTrue();

        var recovered = _supervisor.RecoverStalePidFile(handle.PidFilePath);

        recovered.Should().BeTrue();
        File.Exists(handle.PidFilePath).Should().BeFalse();
        _supervisor.IsRunning(handle).Should().BeFalse();
    }

    [Fact]
    public void RecoverStalePidFile_NoFile_ReturnsFalse()
    {
        var missing = Path.Combine(_tempRoot, "does-not-exist.pid");
        _supervisor.RecoverStalePidFile(missing).Should().BeFalse();
    }
}
