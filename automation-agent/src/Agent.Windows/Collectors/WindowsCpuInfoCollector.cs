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
            // Count logical processors by enumerating registry subkeys
            using var cpuKey = Microsoft.Win32.Registry.LocalMachine.OpenSubKey(@"HARDWARE\DESCRIPTION\System\CentralProcessor");
            if (cpuKey is not null)
            {
                logicalProcessors = cpuKey.GetSubKeyNames().Length;
                if (logicalProcessors == 0) logicalProcessors = Environment.ProcessorCount;
            }
        }
        catch (Exception ex)
        {
            _logger.LogDebug(ex, "Failed to enumerate CPU logical processors from registry");
        }

        // Physical cores via WMI
        physicalCores = GetPhysicalCoresViaWmi(logicalProcessors);

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

    private int GetPhysicalCoresViaWmi(int fallbackLogical)
    {
        try
        {
            using var searcher = new System.Management.ManagementObjectSearcher(
                "SELECT NumberOfCores FROM Win32_Processor");
            int totalCores = 0;
            foreach (var obj in searcher.Get())
            {
                var cores = obj["NumberOfCores"];
                if (cores is not null)
                    totalCores += Convert.ToInt32(cores);
                obj.Dispose();
            }
            return totalCores > 0 ? totalCores : Math.Max(1, fallbackLogical / 2);
        }
        catch (Exception ex)
        {
            _logger.LogDebug(ex, "Failed to get physical core count via WMI, using estimate");
            return Math.Max(1, fallbackLogical / 2);
        }
    }
}
