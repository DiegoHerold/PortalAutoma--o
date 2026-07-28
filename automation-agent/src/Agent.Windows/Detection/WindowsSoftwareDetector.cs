using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Models;
using Microsoft.Extensions.Logging;
using Microsoft.Win32;

namespace Biason.AutomationAgent.Windows.Detection;

public sealed class WindowsSoftwareDetector : ISoftwareDetector
{
    private readonly ILogger<WindowsSoftwareDetector> _logger;

    public WindowsSoftwareDetector(ILogger<WindowsSoftwareDetector> logger) => _logger = logger;

    public IReadOnlyList<InstalledSoftware> DetectAll()
    {
        var results = new List<InstalledSoftware>
        {
            DetectChrome(),
            DetectEdge(),
            DetectExcel(),
            DetectOffice(),
            DetectWebView2(),
            DetectPowerShell(),
            DetectDominioContabil()
        };

        return results;
    }

    private InstalledSoftware DetectChrome()
    {
        var paths = new[]
        {
            @"C:\Program Files\Google\Chrome\Application\chrome.exe",
            @"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
        };

        return DetectByExecutable("Google Chrome", paths, "browser.chrome",
            @"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe");
    }

    private InstalledSoftware DetectEdge()
    {
        var paths = new[]
        {
            @"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            @"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
        };

        return DetectByExecutable("Microsoft Edge", paths, "browser.edge",
            @"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe");
    }

    private InstalledSoftware DetectExcel()
    {
        // Try common Office paths
        var paths = new[]
        {
            @"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE",
            @"C:\Program Files (x86)\Microsoft Office\root\Office16\EXCEL.EXE",
            @"C:\Program Files\Microsoft Office\Office16\EXCEL.EXE"
        };

        return DetectByExecutable("Microsoft Excel", paths, "office.excel",
            @"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\excel.exe");
    }

    private InstalledSoftware DetectOffice()
    {
        try
        {
            var registryPaths = new[]
            {
                @"SOFTWARE\Microsoft\Office\ClickToRun\Configuration",
                @"SOFTWARE\Microsoft\Office\16.0\Common\InstallRoot"
            };

            foreach (var regPath in registryPaths)
            {
                using var key = Registry.LocalMachine.OpenSubKey(regPath);
                if (key is not null)
                {
                    var version = key.GetValue("VersionToReport") as string
                        ?? key.GetValue("ClientVersionToReport") as string;
                    return new InstalledSoftware
                    {
                        Name = "Microsoft Office",
                        Version = version,
                        Source = "windows_registry",
                        IsInstalled = true
                    };
                }
            }
        }
        catch (Exception ex)
        {
            _logger.LogDebug(ex, "Failed to detect Office");
        }

        return new InstalledSoftware { Name = "Microsoft Office", IsInstalled = false, Source = "windows_registry" };
    }

    private InstalledSoftware DetectWebView2()
    {
        try
        {
            var regPaths = new[]
            {
                @"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
                @"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
            };

            foreach (var regPath in regPaths)
            {
                using var key = Registry.LocalMachine.OpenSubKey(regPath);
                var version = key?.GetValue("pv") as string;
                if (!string.IsNullOrEmpty(version))
                {
                    return new InstalledSoftware
                    {
                        Name = "WebView2",
                        Version = version,
                        Source = "windows_registry",
                        IsInstalled = true
                    };
                }
            }
        }
        catch (Exception ex)
        {
            _logger.LogDebug(ex, "Failed to detect WebView2");
        }

        return new InstalledSoftware { Name = "WebView2", IsInstalled = false, Source = "windows_registry" };
    }

    private InstalledSoftware DetectPowerShell()
    {
        var paths = new[]
        {
            @"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
            @"C:\Program Files\PowerShell\7\pwsh.exe"
        };

        string? foundPath = null;
        string? version = null;

        foreach (var p in paths)
        {
            if (File.Exists(p))
            {
                foundPath = p;
                try
                {
                    var versionInfo = System.Diagnostics.FileVersionInfo.GetVersionInfo(p);
                    version = versionInfo.ProductVersion;
                }
                catch { /* ignore */ }
                break;
            }
        }

        return new InstalledSoftware
        {
            Name = "PowerShell",
            Version = version,
            ExecutablePath = foundPath,
            Source = "filesystem",
            IsInstalled = foundPath is not null
        };
    }

    private InstalledSoftware DetectDominioContabil()
    {
        try
        {
            // Domínio Contábil - common paths and registry keys
            var paths = new[]
            {
                @"C:\Contabil\Dominio.exe",
                @"C:\Contabil\contabil.exe",
                @"C:\Thomson\Dominio.exe",
                @"D:\Contabil\Dominio.exe"
            };

            foreach (var p in paths)
            {
                if (File.Exists(p))
                {
                    string? version = null;
                    try
                    {
                        var vi = System.Diagnostics.FileVersionInfo.GetVersionInfo(p);
                        version = vi.ProductVersion;
                    }
                    catch { /* ignore */ }

                    return new InstalledSoftware
                    {
                        Name = "Dominio Contabil",
                        Version = version,
                        ExecutablePath = p,
                        Source = "filesystem",
                        IsInstalled = true
                    };
                }
            }

            // Try registry
            var regPaths = new[]
            {
                @"SOFTWARE\Thomson\Dominio",
                @"SOFTWARE\WOW6432Node\Thomson\Dominio"
            };

            foreach (var regPath in regPaths)
            {
                using var key = Registry.LocalMachine.OpenSubKey(regPath);
                if (key is not null)
                {
                    var installPath = key.GetValue("InstallPath") as string;
                    return new InstalledSoftware
                    {
                        Name = "Dominio Contabil",
                        ExecutablePath = installPath,
                        Source = "windows_registry",
                        IsInstalled = true
                    };
                }
            }
        }
        catch (Exception ex)
        {
            _logger.LogDebug(ex, "Failed to detect Dominio Contabil");
        }

        return new InstalledSoftware { Name = "Dominio Contabil", IsInstalled = false, Source = "filesystem" };
    }

    private InstalledSoftware DetectByExecutable(string name, string[] knownPaths, string capabilityKey, string? registryAppPath)
    {
        // Try registry first
        if (registryAppPath is not null)
        {
            try
            {
                using var key = Registry.LocalMachine.OpenSubKey(registryAppPath);
                var regExePath = key?.GetValue(null) as string ?? key?.GetValue("Path") as string;
                if (!string.IsNullOrEmpty(regExePath) && File.Exists(regExePath))
                {
                    string? version = null;
                    try
                    {
                        var vi = System.Diagnostics.FileVersionInfo.GetVersionInfo(regExePath);
                        version = vi.ProductVersion;
                    }
                    catch { /* ignore */ }

                    return new InstalledSoftware
                    {
                        Name = name,
                        Version = version,
                        ExecutablePath = regExePath,
                        Source = "windows_registry",
                        IsInstalled = true
                    };
                }
            }
            catch (Exception ex)
            {
                _logger.LogDebug(ex, "Failed to check registry for {Software}", name);
            }
        }

        // Then try known paths
        foreach (var p in knownPaths)
        {
            if (File.Exists(p))
            {
                string? version = null;
                try
                {
                    var vi = System.Diagnostics.FileVersionInfo.GetVersionInfo(p);
                    version = vi.ProductVersion;
                }
                catch { /* ignore */ }

                return new InstalledSoftware
                {
                    Name = name,
                    Version = version,
                    ExecutablePath = p,
                    Source = "filesystem",
                    IsInstalled = true
                };
            }
        }

        return new InstalledSoftware { Name = name, IsInstalled = false, Source = "filesystem" };
    }
}
