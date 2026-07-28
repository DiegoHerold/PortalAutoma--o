using System.Runtime.InteropServices;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models;
using Microsoft.Extensions.Logging;

namespace Biason.AutomationAgent.Windows.Collectors;

public sealed class WindowsSessionInfoCollector : ISessionInfoCollector
{
    private readonly ILogger<WindowsSessionInfoCollector> _logger;

    public WindowsSessionInfoCollector(ILogger<WindowsSessionInfoCollector> logger) => _logger = logger;

    [DllImport("user32.dll")]
    private static extern int GetSystemMetrics(int nIndex);

    private const int SM_CXSCREEN = 0;
    private const int SM_CYSCREEN = 1;
    private const int SM_CMONITORS = 80;

    public SessionInfo Collect()
    {
        try
        {
            var sessionId = System.Diagnostics.Process.GetCurrentProcess().SessionId;
            var user = Environment.UserName;
            var domain = Environment.UserDomainName;
            var fullUser = string.IsNullOrEmpty(domain) ? user : $"{domain}\\{user}";

            // Detect session type
            var sessionType = SessionType.Local;
            var sessionName = Environment.GetEnvironmentVariable("SESSIONNAME");
            if (!string.IsNullOrEmpty(sessionName) && sessionName.StartsWith("RDP", StringComparison.OrdinalIgnoreCase))
                sessionType = SessionType.Rdp;

            // Screen resolution
            int? width = null, height = null, monitors = null;
            try
            {
                width = GetSystemMetrics(SM_CXSCREEN);
                height = GetSystemMetrics(SM_CYSCREEN);
                monitors = GetSystemMetrics(SM_CMONITORS);
                if (width == 0) width = null;
                if (height == 0) height = null;
                if (monitors == 0) monitors = null;
            }
            catch { /* P/Invoke may fail on non-interactive sessions */ }

            // Lock state detection
            bool? isLocked = null;
            try
            {
                // Heuristic: if desktop can be opened, session is unlocked
                var desktop = OpenInputDesktop(0, false, 0x0001);
                if (desktop != IntPtr.Zero)
                {
                    isLocked = false;
                    CloseDesktop(desktop);
                }
                else
                {
                    isLocked = true;
                }
            }
            catch
            {
                isLocked = null;
            }

            return new SessionInfo
            {
                Status = sessionId >= 0 ? SessionStatus.Available : SessionStatus.NoSession,
                IsLocked = isLocked,
                User = fullUser,
                SessionId = sessionId,
                Type = sessionType,
                ScreenWidth = width,
                ScreenHeight = height,
                MonitorCount = monitors
            };
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to collect session info");
            return new SessionInfo
            {
                Status = SessionStatus.Unknown,
                Type = SessionType.Unknown
            };
        }
    }

    [DllImport("user32.dll", SetLastError = true)]
    private static extern IntPtr OpenInputDesktop(uint dwFlags, bool fInherit, uint dwDesiredAccess);

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool CloseDesktop(IntPtr hDesktop);
}
