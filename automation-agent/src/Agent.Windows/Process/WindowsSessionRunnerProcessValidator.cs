using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Contracts;
using Microsoft.Extensions.Options;

namespace Biason.AutomationAgent.Windows.Process;

public sealed class WindowsSessionRunnerProcessValidator : ISessionRunnerProcessValidator
{
    private readonly SessionRunnerOptions _options;

    public WindowsSessionRunnerProcessValidator(IOptions<SessionRunnerOptions> options) => _options = options.Value;

    private const uint ProcessQueryLimitedInformation = 0x1000;

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool ProcessIdToSessionId(int dwProcessId, out int pSessionId);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern IntPtr OpenProcess(uint dwDesiredAccess, bool bInheritHandle, int dwProcessId);

    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern bool QueryFullProcessImageName(IntPtr hProcess, int dwFlags, StringBuilder lpExeName, ref int lpdwSize);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool CloseHandle(IntPtr hObject);

    public Task<SessionRunnerProcessValidationResult> ValidateAsync(
        int actualProcessId,
        int declaredProcessId,
        int declaredSessionId,
        CancellationToken ct = default)
    {
        if (actualProcessId <= 0)
        {
            return Task.FromResult(SessionRunnerProcessValidationResult.Invalid(
                "INVALID_CLIENT_PID",
                "Could not determine the actual named-pipe client PID."));
        }

        if (declaredProcessId != actualProcessId)
        {
            return Task.FromResult(SessionRunnerProcessValidationResult.Invalid(
                "INVALID_CLIENT_PID",
                $"Declared PID {declaredProcessId} does not match actual PID {actualProcessId}."));
        }

        var actualSessionId = GetSessionId(actualProcessId);
        if (actualSessionId is null)
        {
            return Task.FromResult(SessionRunnerProcessValidationResult.Invalid(
                "INVALID_RUNNER_PROCESS",
                "Could not determine Session Runner process session."));
        }

        if (actualSessionId.Value != declaredSessionId)
        {
            return Task.FromResult(SessionRunnerProcessValidationResult.Invalid(
                "SESSION_ID_MISMATCH",
                $"Declared session {declaredSessionId} does not match actual session {actualSessionId.Value}.",
                actualSessionId: actualSessionId));
        }

        var path = GetProcessImagePath(actualProcessId);
        if (!IsExpectedRunnerPath(path))
        {
            return Task.FromResult(SessionRunnerProcessValidationResult.Invalid(
                "INVALID_RUNNER_PATH",
                "The connected process is not the expected SessionRunner.exe.",
                path,
                actualSessionId));
        }

        return Task.FromResult(SessionRunnerProcessValidationResult.Valid(path, actualSessionId.Value));
    }

    private static int? GetSessionId(int processId)
    {
        try
        {
            if (!OperatingSystem.IsWindows())
                return global::System.Diagnostics.Process.GetProcessById(processId).SessionId;

            return ProcessIdToSessionId(processId, out var sessionId) ? sessionId : null;
        }
        catch
        {
            return null;
        }
    }

    private static string? GetProcessImagePath(int processId)
    {
        try
        {
            if (!OperatingSystem.IsWindows())
                return global::System.Diagnostics.Process.GetProcessById(processId).MainModule?.FileName;

            var handle = OpenProcess(ProcessQueryLimitedInformation, false, processId);
            if (handle == IntPtr.Zero) return null;
            try
            {
                var size = 32768;
                var builder = new StringBuilder(size);
                return QueryFullProcessImageName(handle, 0, builder, ref size) ? builder.ToString() : null;
            }
            finally
            {
                CloseHandle(handle);
            }
        }
        catch
        {
            return null;
        }
    }

    private bool IsExpectedRunnerPath(string? path)
    {
        if (string.IsNullOrWhiteSpace(path)) return false;

        var expected = string.IsNullOrWhiteSpace(_options.ExpectedExecutablePath)
            ? Path.Combine(AppContext.BaseDirectory, "SessionRunner.exe")
            : _options.ExpectedExecutablePath!;

        if (string.Equals(Path.GetFullPath(path), Path.GetFullPath(expected), StringComparison.OrdinalIgnoreCase))
            return true;

        return string.Equals(Path.GetFileName(path), "SessionRunner.exe", StringComparison.OrdinalIgnoreCase) &&
               string.IsNullOrWhiteSpace(_options.ExpectedExecutablePath);
    }
}
