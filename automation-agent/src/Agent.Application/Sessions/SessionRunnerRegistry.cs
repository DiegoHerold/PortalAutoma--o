using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Sessions;
using Biason.AutomationAgent.Protocol.Serialization;
using Microsoft.Extensions.Options;

namespace Biason.AutomationAgent.Application.Sessions;

public sealed class SessionRunnerRegistry : ISessionRunnerRegistry
{
    private readonly ISessionRunnerRepository _runners;
    private readonly IInteractiveSessionRepository _sessions;
    private readonly ISessionEventRepository _events;
    private readonly IClock _clock;
    private readonly SessionRunnerOptions _options;
    private readonly Dictionary<string, SessionTokenState> _tokens = new(StringComparer.Ordinal);
    private readonly SemaphoreSlim _gate = new(1, 1);

    public SessionRunnerRegistry(
        ISessionRunnerRepository runners,
        IInteractiveSessionRepository sessions,
        ISessionEventRepository events,
        IClock clock,
        IOptions<SessionRunnerOptions> options)
    {
        _runners = runners;
        _sessions = sessions;
        _events = events;
        _clock = clock;
        _options = options.Value;
    }

    public async Task RegisterAsync(SessionRunnerRecord runner, CancellationToken ct = default)
    {
        await _gate.WaitAsync(ct);
        try
        {
            runner.State = SessionRunnerConnectionState.Connected;
            await _runners.UpsertAsync(runner, ct);
            await _sessions.AttachRunnerAsync(runner.SessionId, runner.InstanceId, _clock.UtcNow, ct);
            await _events.AddAsync(new SessionEventRecord
            {
                SessionId = runner.SessionId,
                SessionRunnerInstanceId = runner.InstanceId,
                EventType = "session.runner_registered",
                DetailJson = ProtocolJson.Serialize(new { runner.ProcessId, runner.Version }),
                OccurredAtUtc = _clock.UtcNow
            }, ct);
        }
        finally
        {
            _gate.Release();
        }
    }

    public async Task RecordHeartbeatAsync(string instanceId, DateTime heartbeatAtUtc, DesktopState desktop, CancellationToken ct = default)
    {
        await _runners.UpdateHeartbeatAsync(instanceId, heartbeatAtUtc, desktop, ct);
        var runner = await _runners.GetAsync(instanceId, ct);
        if (runner is null) return;

        var currentSession = await _sessions.GetAsync(runner.SessionId, ct);
        if (currentSession is not null)
        {
            await _sessions.UpsertAsync(new InteractiveSessionRecord
            {
                SessionId = currentSession.SessionId,
                UserName = currentSession.UserName,
                DomainName = currentSession.DomainName,
                StationName = currentSession.StationName,
                SessionType = currentSession.SessionType,
                State = desktop.Locked == true
                    ? WindowsSessionState.Locked
                    : currentSession.State == WindowsSessionState.Locked ? WindowsSessionState.Active : currentSession.State,
                IsLocked = desktop.Locked ?? currentSession.IsLocked,
                ScreenWidth = desktop.Resolution?.Width ?? currentSession.ScreenWidth,
                ScreenHeight = desktop.Resolution?.Height ?? currentSession.ScreenHeight,
                MonitorCount = desktop.MonitorCount ?? currentSession.MonitorCount,
                DpiScale = desktop.DpiScale ?? currentSession.DpiScale,
                SessionRunnerInstanceId = instanceId,
                ObservedAtUtc = heartbeatAtUtc
            }, ct);
        }
    }

    public async Task MarkDisconnectedAsync(string instanceId, string reason, CancellationToken ct = default)
    {
        await _gate.WaitAsync(ct);
        try
        {
            var runner = await _runners.GetAsync(instanceId, ct);
            InvalidateSessionToken(instanceId);
            if (runner is not null)
            {
                await _runners.MarkDisconnectedAsync(instanceId, _clock.UtcNow, reason, ct);
                await _sessions.AttachRunnerAsync(runner.SessionId, null, _clock.UtcNow, ct);
                await _events.AddAsync(new SessionEventRecord
                {
                    SessionId = runner.SessionId,
                    SessionRunnerInstanceId = instanceId,
                    EventType = "session.runner_disconnected",
                    DetailJson = ProtocolJson.Serialize(new { reason }),
                    OccurredAtUtc = _clock.UtcNow
                }, ct);
            }
        }
        finally
        {
            _gate.Release();
        }
    }

    public async Task MarkTimedOutAsync(DateTime nowUtc, CancellationToken ct = default)
    {
        var connected = await _runners.GetConnectedAsync(ct);
        var timeout = TimeSpan.FromSeconds(_options.DisconnectTimeoutSeconds);
        foreach (var runner in connected)
        {
            var last = runner.LastHeartbeatAtUtc ?? runner.RegisteredAtUtc;
            if (nowUtc - last > timeout)
                await MarkDisconnectedAsync(runner.InstanceId, "heartbeat_timeout", ct);
        }
    }

    public async Task<IReadOnlyList<SessionRunnerRecord>> GetSnapshotAsync(CancellationToken ct = default)
        => await _runners.GetAllAsync(ct);

    public string IssueSessionToken(string instanceId, int sessionId, int processId, DateTime expiresAtUtc, out string fingerprint)
    {
        var token = SessionTokenHasher.NewToken("sr_token");
        fingerprint = SessionTokenHasher.Fingerprint(token);
        lock (_tokens)
        {
            _tokens[instanceId] = new SessionTokenState(token, fingerprint, sessionId, processId, expiresAtUtc);
        }
        return token;
    }

    public bool TryValidateSessionToken(string token, string instanceId, int sessionId, int processId, DateTime nowUtc)
    {
        if (string.IsNullOrWhiteSpace(token)) return false;
        var fingerprint = SessionTokenHasher.Fingerprint(token);
        lock (_tokens)
        {
            return _tokens.TryGetValue(instanceId, out var state) &&
                   state.SessionId == sessionId &&
                   state.ProcessId == processId &&
                   state.ExpiresAtUtc > nowUtc &&
                   string.Equals(state.Fingerprint, fingerprint, StringComparison.Ordinal);
        }
    }

    public bool TryGetSessionToken(string instanceId, out string token)
    {
        lock (_tokens)
        {
            if (_tokens.TryGetValue(instanceId, out var state) && state.ExpiresAtUtc > _clock.UtcNow)
            {
                token = state.Token;
                return true;
            }
        }

        token = string.Empty;
        return false;
    }

    public void InvalidateSessionToken(string instanceId)
    {
        lock (_tokens) { _tokens.Remove(instanceId); }
    }

    private sealed record SessionTokenState(string Token, string Fingerprint, int SessionId, int ProcessId, DateTime ExpiresAtUtc);
}
