using System.Runtime.InteropServices;
using Biason.AutomationAgent.Domain.Contracts;
using Microsoft.Extensions.Logging;

namespace Biason.AutomationAgent.Windows.Collectors;

/// <summary>
/// Measures CPU usage by comparing two snapshots of system idle/kernel/user times.
/// Uses GetSystemTimes Win32 API — no PerformanceCounter dependency.
/// </summary>
public sealed class WindowsCpuUsageCollector : ICpuUsageProvider, IDisposable
{
    private readonly ILogger<WindowsCpuUsageCollector> _logger;
    private readonly object _lock = new();
    private long _prevIdleTime;
    private long _prevKernelTime;
    private long _prevUserTime;
    private double _lastCpuPercent;
    private bool _initialized;

    public WindowsCpuUsageCollector(ILogger<WindowsCpuUsageCollector> logger)
    {
        _logger = logger;
        TakeSnapshot();
    }

    public double GetCpuUsagePercent()
    {
        lock (_lock)
        {
            try
            {
                if (!GetSystemTimes(out var idleTime, out var kernelTime, out var userTime))
                {
                    _logger.LogDebug("GetSystemTimes failed, returning last known value");
                    return _lastCpuPercent;
                }

                long idle = idleTime.ToTicks();
                long kernel = kernelTime.ToTicks();
                long user = userTime.ToTicks();

                if (!_initialized)
                {
                    _prevIdleTime = idle;
                    _prevKernelTime = kernel;
                    _prevUserTime = user;
                    _initialized = true;
                    return 0;
                }

                long idleDelta = idle - _prevIdleTime;
                long kernelDelta = kernel - _prevKernelTime;
                long userDelta = user - _prevUserTime;
                long totalSystem = kernelDelta + userDelta;

                _prevIdleTime = idle;
                _prevKernelTime = kernel;
                _prevUserTime = user;

                if (totalSystem <= 0)
                    return _lastCpuPercent;

                // kernel time includes idle time
                double cpuPercent = (1.0 - ((double)idleDelta / totalSystem)) * 100.0;
                cpuPercent = Math.Clamp(cpuPercent, 0, 100);
                _lastCpuPercent = Math.Round(cpuPercent, 1);
                return _lastCpuPercent;
            }
            catch (Exception ex)
            {
                _logger.LogDebug(ex, "Failed to calculate CPU usage");
                return _lastCpuPercent;
            }
        }
    }

    private void TakeSnapshot()
    {
        try
        {
            if (GetSystemTimes(out var idleTime, out var kernelTime, out var userTime))
            {
                _prevIdleTime = idleTime.ToTicks();
                _prevKernelTime = kernelTime.ToTicks();
                _prevUserTime = userTime.ToTicks();
                _initialized = true;
            }
        }
        catch (Exception ex)
        {
            _logger.LogDebug(ex, "Failed to take initial CPU snapshot");
        }
    }

    public void Dispose() { }

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool GetSystemTimes(
        out FILETIME lpIdleTime,
        out FILETIME lpKernelTime,
        out FILETIME lpUserTime);

    [StructLayout(LayoutKind.Sequential)]
    private struct FILETIME
    {
        public uint dwLowDateTime;
        public uint dwHighDateTime;
        public readonly long ToTicks() => ((long)dwHighDateTime << 32) | dwLowDateTime;
    }
}
