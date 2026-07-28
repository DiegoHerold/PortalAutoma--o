using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Models;
using Microsoft.Extensions.Logging;

namespace Biason.AutomationAgent.Windows.Collectors;

public sealed class WindowsCpuInfoCollector : ICpuInfoCollector
{
    private readonly ILogger<WindowsCpuInfoCollector> _logger;

    public WindowsCpuInfoCollector(ILogger<WindowsCpuInfoCollector> logger) => _logger = logger;

    public CpuInfo Collect()
    {
        string model = "Unknown";
        string? manufacturer = null;
        string architecture = "x64";
        int physicalCores = Environment.ProcessorCount;
        int logicalProcessors = Environment.ProcessorCount;
        int? frequencyMhz = null;

        try
        {
            using var key = Microsoft.Win32.Registry.LocalMachine.OpenSubKey(@"HARDWARE\DESCRIPTION\System\CentralProcessor\0");
            if (key is not null)
            {
                model = key.GetValue("ProcessorNameString") as string ?? model;
                manufacturer = key.GetValue("VendorIdentifier") as string;
                var mhz = key.GetValue("~MHz");
                if (mhz is int freq)
                    frequencyMhz = freq;
            }
        }
        catch (Exception ex)
        {
            _logger.LogDebug(ex, "Failed to read CPU info from registry");
        }

        try
        {
            // Count physical cores by enumerating registry subkeys
            using var cpuKey = Microsoft.Win32.Registry.LocalMachine.OpenSubKey(@"HARDWARE\DESCRIPTION\System\CentralProcessor");
            if (cpuKey is not null)
            {
                logicalProcessors = cpuKey.GetSubKeyNames().Length;
                if (logicalProcessors == 0) logicalProcessors = Environment.ProcessorCount;
            }

            // Physical cores via environment - rough estimate
            // On Windows, without WMI we use logical / 2 for hyper-threaded CPUs as approximation
            physicalCores = Math.Max(1, logicalProcessors / 2);
        }
        catch (Exception ex)
        {
            _logger.LogDebug(ex, "Failed to enumerate CPU cores");
        }

        return new CpuInfo
        {
            Manufacturer = manufacturer,
            Model = model.Trim(),
            Architecture = architecture,
            PhysicalCores = physicalCores,
            LogicalProcessors = logicalProcessors,
            FrequencyMhz = frequencyMhz
        };
    }
}
