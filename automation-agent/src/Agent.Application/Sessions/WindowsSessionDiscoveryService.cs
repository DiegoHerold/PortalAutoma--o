using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Models.Sessions;
using Biason.AutomationAgent.Protocol.Serialization;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

namespace Biason.AutomationAgent.Application.Sessions;

public sealed class WindowsSessionDiscoveryService : BackgroundService
{
    private readonly IWindowsSessionDiscovery _discovery;
    private readonly IInteractiveSessionRepository _sessions;
    private readonly ISessionEventRepository _events;
    private readonly ISessionRunnerRegistry _registry;
    private readonly IClock _clock;
    private readonly ILogger<WindowsSessionDiscoveryService> _logger;

    public WindowsSessionDiscoveryService(
        IWindowsSessionDiscovery discovery,
        IInteractiveSessionRepository sessions,
        ISessionEventRepository events,
        ISessionRunnerRegistry registry,
        IClock clock,
        ILogger<WindowsSessionDiscoveryService> logger)
    {
        _discovery = discovery;
        _sessions = sessions;
        _events = events;
        _registry = registry;
        _clock = clock;
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                await RefreshOnceAsync(stoppingToken);
                await _registry.MarkTimedOutAsync(_clock.UtcNow, stoppingToken);
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
            {
                break;
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Windows session discovery cycle failed.");
            }

            try { await Task.Delay(TimeSpan.FromSeconds(10), stoppingToken); }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested) { break; }
        }
    }

    public async Task RefreshOnceAsync(CancellationToken ct = default)
    {
        var sessions = await _discovery.DiscoverAsync(ct);
        foreach (var session in sessions)
        {
            await _sessions.UpsertAsync(ToRecord(session), ct);
            await _events.AddAsync(new SessionEventRecord
            {
                SessionId = session.SessionId,
                EventType = "session.discovered",
                DetailJson = ProtocolJson.Serialize(new
                {
                    state = session.State,
                    type = session.Type,
                    session.IsConsole,
                    session.IsRdp
                }),
                OccurredAtUtc = _clock.UtcNow
            }, ct);
        }
    }

    private static InteractiveSessionRecord ToRecord(WindowsSession session) => new()
    {
        SessionId = session.SessionId,
        UserName = session.User,
        DomainName = session.Domain,
        StationName = session.StationName,
        SessionType = session.Type,
        State = session.State,
        IsLocked = session.Desktop.Locked ?? (session.State == Biason.AutomationAgent.Domain.Enums.WindowsSessionState.Locked ? true : null),
        ScreenWidth = session.Desktop.Resolution?.Width,
        ScreenHeight = session.Desktop.Resolution?.Height,
        MonitorCount = session.Desktop.MonitorCount,
        DpiScale = session.Desktop.DpiScale,
        ObservedAtUtc = session.ObservedAtUtc
    };
}
