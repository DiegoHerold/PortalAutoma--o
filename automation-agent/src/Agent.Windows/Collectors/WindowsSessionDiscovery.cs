using System.Diagnostics;
using System.Runtime.InteropServices;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Sessions;
using Microsoft.Extensions.Logging;

namespace Biason.AutomationAgent.Windows.Collectors;

public sealed class WindowsSessionDiscovery : IWindowsSessionDiscovery
{
    private readonly IDesktopStateReader _desktop;
    private readonly ILogger<WindowsSessionDiscovery> _logger;

    public WindowsSessionDiscovery(IDesktopStateReader desktop, ILogger<WindowsSessionDiscovery> logger)
    {
        _desktop = desktop;
        _logger = logger;
    }

    private static readonly IntPtr WtsCurrentServer = IntPtr.Zero;

    [DllImport("kernel32.dll")]
    private static extern uint WTSGetActiveConsoleSessionId();

    [DllImport("wtsapi32.dll", SetLastError = true)]
    private static extern bool WTSEnumerateSessions(
        IntPtr hServer,
        int reserved,
        int version,
        out IntPtr ppSessionInfo,
        out int pCount);

    [DllImport("wtsapi32.dll")]
    private static extern void WTSFreeMemory(IntPtr pMemory);

    [DllImport("wtsapi32.dll", SetLastError = true)]
    private static extern bool WTSQuerySessionInformation(
        IntPtr hServer,
        int sessionId,
        WtsInfoClass wtsInfoClass,
        out IntPtr ppBuffer,
        out int pBytesReturned);

    [StructLayout(LayoutKind.Sequential)]
    private readonly struct WtsSessionInfo
    {
        public readonly int SessionId;
        public readonly IntPtr StationName;
        public readonly WtsConnectState State;
    }

    private enum WtsInfoClass
    {
        WTSUserName = 5,
        WTSWinStationName = 6,
        WTSDomainName = 7,
        WTSClientProtocolType = 16
    }

    private enum WtsConnectState
    {
        WTSActive,
        WTSConnected,
        WTSConnectQuery,
        WTSShadow,
        WTSDisconnected,
        WTSIdle,
        WTSListen,
        WTSReset,
        WTSDown,
        WTSInit
    }

    public Task<IReadOnlyList<WindowsSession>> DiscoverAsync(CancellationToken ct = default)
    {
        try
        {
            if (!OperatingSystem.IsWindows())
                return Task.FromResult<IReadOnlyList<WindowsSession>>(new[] { BuildFallbackSession() });

            if (!WTSEnumerateSessions(WtsCurrentServer, 0, 1, out var sessionInfoPtr, out var count))
                return Task.FromResult<IReadOnlyList<WindowsSession>>(new[] { BuildFallbackSession() });

            try
            {
                var sessions = new List<WindowsSession>();
                var consoleSessionId = GetActiveConsoleSessionId();
                var structSize = Marshal.SizeOf<WtsSessionInfo>();
                var now = DateTime.UtcNow;
                var currentProcessSession = global::System.Diagnostics.Process.GetCurrentProcess().SessionId;

                for (var i = 0; i < count; i++)
                {
                    ct.ThrowIfCancellationRequested();
                    var itemPtr = IntPtr.Add(sessionInfoPtr, i * structSize);
                    var info = Marshal.PtrToStructure<WtsSessionInfo>(itemPtr);
                    var protocol = QueryProtocol(info.SessionId);
                    var state = MapState(info.State);
                    var desktop = info.SessionId == currentProcessSession ? _desktop.ReadCurrent() : DesktopState.Unknown;
                    if (desktop.Locked == true && state == WindowsSessionState.Active)
                        state = WindowsSessionState.Locked;

                    sessions.Add(new WindowsSession
                    {
                        SessionId = info.SessionId,
                        User = QueryString(info.SessionId, WtsInfoClass.WTSUserName),
                        Domain = QueryString(info.SessionId, WtsInfoClass.WTSDomainName),
                        StationName = QueryString(info.SessionId, WtsInfoClass.WTSWinStationName)
                            ?? Marshal.PtrToStringAuto(info.StationName),
                        State = state,
                        Type = protocol == 2 ? SessionType.Rdp : SessionType.Local,
                        IsConsole = consoleSessionId.HasValue && info.SessionId == consoleSessionId.Value,
                        IsRdp = protocol == 2,
                        Desktop = desktop,
                        ObservedAtUtc = now
                    });
                }

                return Task.FromResult<IReadOnlyList<WindowsSession>>(sessions);
            }
            finally
            {
                WTSFreeMemory(sessionInfoPtr);
            }
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "WTS session discovery failed; using current-process fallback.");
            return Task.FromResult<IReadOnlyList<WindowsSession>>(new[] { BuildFallbackSession() });
        }
    }

    public int? GetActiveConsoleSessionId()
    {
        try
        {
            if (!OperatingSystem.IsWindows()) return null;
            var sessionId = WTSGetActiveConsoleSessionId();
            return sessionId == 0xFFFFFFFF ? null : unchecked((int)sessionId);
        }
        catch
        {
            return null;
        }
    }

    private WindowsSession BuildFallbackSession()
    {
        var desktop = _desktop.ReadCurrent();
        var sessionName = Environment.GetEnvironmentVariable("SESSIONNAME");
        var isRdp = !string.IsNullOrWhiteSpace(sessionName) &&
                    sessionName.StartsWith("RDP", StringComparison.OrdinalIgnoreCase);
        var locked = desktop.Locked == true;
        return new WindowsSession
        {
            SessionId = global::System.Diagnostics.Process.GetCurrentProcess().SessionId,
            User = Environment.UserName,
            Domain = Environment.UserDomainName,
            StationName = sessionName,
            State = locked ? WindowsSessionState.Locked : WindowsSessionState.Active,
            Type = isRdp ? SessionType.Rdp : SessionType.Local,
            IsConsole = !isRdp,
            IsRdp = isRdp,
            Desktop = desktop,
            ObservedAtUtc = DateTime.UtcNow
        };
    }

    private static WindowsSessionState MapState(WtsConnectState state) => state switch
    {
        WtsConnectState.WTSActive => WindowsSessionState.Active,
        WtsConnectState.WTSConnected => WindowsSessionState.Connected,
        WtsConnectState.WTSDisconnected => WindowsSessionState.Disconnected,
        WtsConnectState.WTSIdle => WindowsSessionState.Idle,
        WtsConnectState.WTSDown => WindowsSessionState.Terminated,
        _ => WindowsSessionState.Unknown
    };

    private static string? QueryString(int sessionId, WtsInfoClass infoClass)
    {
        if (!WTSQuerySessionInformation(WtsCurrentServer, sessionId, infoClass, out var buffer, out _))
            return null;

        try
        {
            return Marshal.PtrToStringAuto(buffer);
        }
        finally
        {
            WTSFreeMemory(buffer);
        }
    }

    private static int QueryProtocol(int sessionId)
    {
        if (!WTSQuerySessionInformation(WtsCurrentServer, sessionId, WtsInfoClass.WTSClientProtocolType, out var buffer, out var bytes))
            return 0;

        try
        {
            return bytes >= 2 ? Marshal.ReadInt16(buffer) : 0;
        }
        finally
        {
            WTSFreeMemory(buffer);
        }
    }
}
