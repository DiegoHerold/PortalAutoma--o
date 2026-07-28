using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Security.Principal;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Models;
using Microsoft.Extensions.Logging;

namespace Biason.AutomationAgent.Windows.Collectors;

public sealed class WindowsOsInfoCollector : IOsInfoCollector
{
    private readonly ILogger<WindowsOsInfoCollector> _logger;
    private readonly string _agentVersion;

    public WindowsOsInfoCollector(ILogger<WindowsOsInfoCollector> logger, string agentVersion = "0.1.0")
    {
        _logger = logger;
        _agentVersion = agentVersion;
    }

    public OsInfo Collect()
    {
        try
        {
            var osVersion = Environment.OSVersion;
            var name = RuntimeInformation.OSDescription;
            string? edition = null;
            string? build = null;

            try
            {
                using var key = Microsoft.Win32.Registry.LocalMachine.OpenSubKey(@"SOFTWARE\Microsoft\Windows NT\CurrentVersion");
                if (key is not null)
                {
                    edition = key.GetValue("EditionID") as string;
                    build = key.GetValue("CurrentBuildNumber") as string;
                    var displayVersion = key.GetValue("DisplayVersion") as string;
                    var productName = key.GetValue("ProductName") as string;
                    if (!string.IsNullOrEmpty(productName))
                        name = productName;
                }
            }
            catch (Exception ex)
            {
                _logger.LogDebug(ex, "Failed to read Windows registry for OS info");
            }

            bool isElevated;
            try
            {
                using var identity = WindowsIdentity.GetCurrent();
                var principal = new WindowsPrincipal(identity);
                isElevated = principal.IsInRole(WindowsBuiltInRole.Administrator);
            }
            catch
            {
                isElevated = false;
            }

            string? domain = null;
            try
            {
                domain = Environment.UserDomainName;
            }
            catch { /* ignore */ }

            return new OsInfo
            {
                Name = name,
                Edition = edition,
                Version = osVersion.Version.ToString(),
                Build = build,
                Architecture = RuntimeInformation.OSArchitecture.ToString().ToLowerInvariant(),
                Hostname = Environment.MachineName,
                DomainOrWorkgroup = domain,
                UptimeSeconds = Environment.TickCount64 / 1000,
                IsElevated = isElevated,
                AgentVersion = _agentVersion
            };
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to collect OS info");
            return new OsInfo
            {
                Name = "Unknown",
                Architecture = RuntimeInformation.OSArchitecture.ToString().ToLowerInvariant(),
                Hostname = Environment.MachineName,
                AgentVersion = _agentVersion
            };
        }
    }
}
