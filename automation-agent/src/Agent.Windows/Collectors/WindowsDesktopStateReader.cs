using System.Runtime.InteropServices;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Models.Sessions;
using Microsoft.Extensions.Logging;

namespace Biason.AutomationAgent.Windows.Collectors;

public sealed class WindowsDesktopStateReader : IDesktopStateReader
{
    private readonly ILogger<WindowsDesktopStateReader> _logger;

    public WindowsDesktopStateReader(ILogger<WindowsDesktopStateReader> logger) => _logger = logger;

    private const int SM_CXSCREEN = 0;
    private const int SM_CYSCREEN = 1;
    private const int SM_CMONITORS = 80;

    [DllImport("user32.dll")]
    private static extern int GetSystemMetrics(int nIndex);

    [DllImport("user32.dll", SetLastError = true)]
    private static extern IntPtr OpenInputDesktop(uint dwFlags, bool fInherit, uint dwDesiredAccess);

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool CloseDesktop(IntPtr hDesktop);

    [DllImport("user32.dll")]
    private static extern uint GetDpiForSystem();

    public DesktopState ReadCurrent()
    {
        try
        {
            bool? locked = null;
            bool? available = null;

            try
            {
                var desktop = OpenInputDesktop(0, false, 0x0001);
                if (desktop != IntPtr.Zero)
                {
                    locked = false;
                    available = true;
                    CloseDesktop(desktop);
                }
                else
                {
                    locked = true;
                    available = false;
                }
            }
            catch
            {
                locked = null;
                available = null;
            }

            int? width = GetMetric(SM_CXSCREEN);
            int? height = GetMetric(SM_CYSCREEN);
            int? monitors = GetMetric(SM_CMONITORS);
            double? dpiScale = null;
            try
            {
                var dpi = GetDpiForSystem();
                if (dpi > 0) dpiScale = Math.Round(dpi / 96d, 2);
            }
            catch { /* unavailable on older Windows builds */ }

            return new DesktopState
            {
                Available = available,
                Locked = locked,
                Resolution = width.HasValue && height.HasValue
                    ? new DesktopResolution { Width = width.Value, Height = height.Value }
                    : null,
                MonitorCount = monitors,
                DpiScale = dpiScale
            };
        }
        catch (Exception ex)
        {
            _logger.LogDebug(ex, "Failed to read desktop state.");
            return DesktopState.Unknown;
        }
    }

    private static int? GetMetric(int metric)
    {
        try
        {
            var value = GetSystemMetrics(metric);
            return value > 0 ? value : null;
        }
        catch
        {
            return null;
        }
    }
}
