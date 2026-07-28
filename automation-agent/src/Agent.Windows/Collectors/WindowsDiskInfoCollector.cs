using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Models;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace Biason.AutomationAgent.Windows.Collectors;

public sealed class WindowsDiskInfoCollector : IDiskInfoCollector
{
    private readonly IDirectoryResolver _dirs;
    private readonly ILogger<WindowsDiskInfoCollector> _logger;
    private readonly StorageOptions _options;

    public WindowsDiskInfoCollector(IDirectoryResolver dirs, IOptions<StorageOptions> options, ILogger<WindowsDiskInfoCollector> logger)
    {
        _dirs = dirs;
        _options = options.Value;
        _logger = logger;
    }

    public DiskInfo Collect()
    {
        try
        {
            var root = Path.GetPathRoot(_dirs.RootPath) ?? "C:\\";
            var drive = new DriveInfo(root);

            return new DiskInfo
            {
                Volume = drive.Name,
                FileSystem = drive.DriveFormat,
                TotalMb = drive.TotalSize / (1024 * 1024),
                FreeMb = drive.AvailableFreeSpace / (1024 * 1024),
                UsagePercent = drive.TotalSize > 0
                    ? Math.Round((double)(drive.TotalSize - drive.AvailableFreeSpace) / drive.TotalSize * 100, 1)
                    : 0,
                DataDirectory = _dirs.RootPath,
                MinimumFreeMb = _options.MinimumFreeDiskMb
            };
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to collect disk info");
            return new DiskInfo
            {
                Volume = "Unknown",
                DataDirectory = _dirs.RootPath,
                MinimumFreeMb = _options.MinimumFreeDiskMb
            };
        }
    }
}
