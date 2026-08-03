using System.Diagnostics;
using System.Runtime.InteropServices;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Models;
using Microsoft.Extensions.Logging;

namespace Biason.AutomationAgent.Windows.Collectors;

public sealed class WindowsMemoryInfoCollector : IMemoryInfoCollector
{
    private readonly ILogger<WindowsMemoryInfoCollector> _logger;

    public WindowsMemoryInfoCollector(ILogger<WindowsMemoryInfoCollector> logger) => _logger = logger;

    [StructLayout(LayoutKind.Sequential)]
    private struct MEMORYSTATUSEX
    {
        public uint dwLength;
        public uint dwMemoryLoad;
        public ulong ullTotalPhys;
        public ulong ullAvailPhys;
        public ulong ullTotalPageFile;
        public ulong ullAvailPageFile;
        public ulong ullTotalVirtual;
        public ulong ullAvailVirtual;
        public ulong ullAvailExtendedVirtual;
    }

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GlobalMemoryStatusEx(ref MEMORYSTATUSEX lpBuffer);

    public MemoryInfo Collect()
    {
        try
        {
            var memStatus = new MEMORYSTATUSEX { dwLength = (uint)Marshal.SizeOf<MEMORYSTATUSEX>() };
            if (GlobalMemoryStatusEx(ref memStatus))
            {
                var totalMb = (long)(memStatus.ullTotalPhys / (1024 * 1024));
                var availMb = (long)(memStatus.ullAvailPhys / (1024 * 1024));
                var usedMb = totalMb - availMb;
                var usagePercent = totalMb > 0 ? Math.Round((double)usedMb / totalMb * 100, 1) : 0;

                long agentMemoryMb = 0;
                try
                {
                    // Totalmente qualificado: nesta árvore de namespaces
                    // (Biason.AutomationAgent.Windows.*), "Process" sem qualificação
                    // resolve para o namespace irmão .Windows.Process (ProcessTreeManager),
                    // não para System.Diagnostics.Process — CS0234.
                    using var proc = System.Diagnostics.Process.GetCurrentProcess();
                    agentMemoryMb = proc.WorkingSet64 / (1024 * 1024);
                }
                catch { /* ignore */ }

                return new MemoryInfo
                {
                    TotalMb = totalMb,
                    AvailableMb = availMb,
                    UsedMb = usedMb,
                    UsagePercent = usagePercent,
                    AgentMemoryMb = agentMemoryMb
                };
            }
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to collect memory info via P/Invoke");
        }

        // Fallback
        try
        {
            var gcInfo = GC.GetGCMemoryInfo();
            var totalMb = gcInfo.TotalAvailableMemoryBytes / (1024 * 1024);
            return new MemoryInfo { TotalMb = totalMb };
        }
        catch
        {
            return new MemoryInfo();
        }
    }

    public double GetCurrentUsagePercent()
    {
        var info = Collect();
        return info.UsagePercent;
    }
}
