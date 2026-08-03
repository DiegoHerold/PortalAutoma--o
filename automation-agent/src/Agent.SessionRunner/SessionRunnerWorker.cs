using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Sessions;
using Biason.AutomationAgent.Protocol.Local;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace Biason.AutomationAgent.SessionRunner;

public sealed class SessionRunnerWorker : BackgroundService
{
    private readonly IWindowsSessionDiscovery _sessions;
    private readonly IDesktopStateReader _desktop;
    private readonly SessionRunnerPipeClient _pipe;
    private readonly InteractiveExecutionHostRunner _hostRunner;
    private readonly SessionRunnerOptions _options;
    private readonly ILogger<SessionRunnerWorker> _logger;
    private readonly string _instanceId = $"sr_{Guid.NewGuid():N}";
    private readonly string _version = typeof(SessionRunnerWorker).Assembly.GetName().Version?.ToString() ?? "0.4.0";

    public SessionRunnerWorker(
        IWindowsSessionDiscovery sessions,
        IDesktopStateReader desktop,
        SessionRunnerPipeClient pipe,
        InteractiveExecutionHostRunner hostRunner,
        IOptions<SessionRunnerOptions> options,
        ILogger<SessionRunnerWorker> logger)
    {
        _sessions = sessions;
        _desktop = desktop;
        _pipe = pipe;
        _hostRunner = hostRunner;
        _options = options.Value;
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        var attempt = 0;
        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                var session = await GetOwnSessionAsync(stoppingToken);
                var desktop = _desktop.ReadCurrent();
                await _pipe.ConnectAsync(stoppingToken);
                var token = await _pipe.AuthenticateAndRegisterAsync(_instanceId, session, desktop, _version, stoppingToken);
                _logger.LogInformation("SESSION_RUNNER_REGISTERED instance={InstanceId} session={SessionId}", _instanceId, session.SessionId);
                attempt = 0;
                await RunConnectedAsync(session, token, stoppingToken);
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
            {
                break;
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "SESSION_RUNNER_CONNECTING Pipe unavailable; reconnecting.");
                attempt++;
                var delay = NextDelay(attempt);
                try { await Task.Delay(delay, stoppingToken); }
                catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested) { break; }
            }
        }
    }

    public override async Task StopAsync(CancellationToken cancellationToken)
    {
        try
        {
            var session = await GetOwnSessionAsync(cancellationToken);
            // Token is intentionally not retained as a field after reconnect loops.
            // A closing pipe will be detected by the Agent Service even when this best-effort
            // stopping message cannot be sent.
        }
        catch { /* best effort */ }

        await base.StopAsync(cancellationToken);
    }

    private async Task RunConnectedAsync(WindowsSession initialSession, string token, CancellationToken ct)
    {
        using var linked = CancellationTokenSource.CreateLinkedTokenSource(ct);
        var heartbeat = RunHeartbeatLoopAsync(initialSession, token, linked.Token);
        var commands = RunCommandLoopAsync(initialSession.SessionId, token, linked.Token);

        var completed = await Task.WhenAny(heartbeat, commands);
        linked.Cancel();
        await completed;
    }

    private async Task RunHeartbeatLoopAsync(WindowsSession initialSession, string token, CancellationToken ct)
    {
        var lastState = initialSession.State;
        var lastLocked = initialSession.Desktop.Locked;
        var sessionId = initialSession.SessionId;

        while (!ct.IsCancellationRequested && _pipe.IsConnected)
        {
            var sessions = await _sessions.DiscoverAsync(ct);
            var current = sessions.FirstOrDefault(s => s.SessionId == sessionId) ?? initialSession;
            var desktop = _desktop.ReadCurrent();
            var state = desktop.Locked == true ? WindowsSessionState.Locked : current.State;

            if (state != lastState || desktop.Locked != lastLocked)
            {
                var eventType = desktop.Locked == true
                    ? "session.locked"
                    : lastLocked == true && desktop.Locked == false ? "session.unlocked" : "session.state_changed";
                await _pipe.SendStateChangedAsync(_instanceId, sessionId, token, eventType, state, desktop, ct);
                lastState = state;
                lastLocked = desktop.Locked;
            }

            await _pipe.SendHeartbeatAsync(_instanceId, sessionId, token, state, desktop, ct);
            await Task.Delay(TimeSpan.FromSeconds(_options.HeartbeatIntervalSeconds), ct);
        }
    }

    private async Task RunCommandLoopAsync(int sessionId, string token, CancellationToken ct)
    {
        while (!ct.IsCancellationRequested && _pipe.IsConnected)
        {
            var envelope = await _pipe.ReadNextAsync(ct);
            if (envelope is null) return;

            switch (envelope.MessageType)
            {
                case LocalMessageTypes.HeartbeatAck:
                    break;

                case LocalMessageTypes.InteractiveExecutionStart:
                    var start = Biason.AutomationAgent.Protocol.Serialization.ProtocolJson.ReadPayload<InteractiveExecutionStartPayload>(envelope.Payload);
                    if (start is not null)
                        await _hostRunner.StartAsync(start, _instanceId, token, _pipe, ct);
                    break;

                case LocalMessageTypes.InteractiveExecutionCancel:
                    var cancel = Biason.AutomationAgent.Protocol.Serialization.ProtocolJson.ReadPayload<InteractiveExecutionCancelPayload>(envelope.Payload);
                    if (cancel is not null)
                        await _hostRunner.CancelAsync(cancel, _instanceId, sessionId, token, _pipe, ct);
                    break;

                case LocalMessageTypes.ProtocolError:
                    _logger.LogWarning("SESSION_RUNNER_PROTOCOL_ERROR {Payload}", envelope.Payload);
                    break;
            }
        }
    }

    private async Task<WindowsSession> GetOwnSessionAsync(CancellationToken ct)
    {
        var sessionId = Environment.ProcessId > 0 ? System.Diagnostics.Process.GetCurrentProcess().SessionId : -1;
        var sessions = await _sessions.DiscoverAsync(ct);
        return sessions.FirstOrDefault(s => s.SessionId == sessionId)
               ?? sessions.FirstOrDefault()
               ?? throw new InvalidOperationException("No Windows session was discovered.");
    }

    private TimeSpan NextDelay(int attempt)
    {
        var min = TimeSpan.FromSeconds(_options.ReconnectInitialDelaySeconds);
        var max = TimeSpan.FromSeconds(_options.ReconnectMaximumDelaySeconds);
        var exponential = TimeSpan.FromSeconds(Math.Min(max.TotalSeconds, min.TotalSeconds * Math.Pow(2, Math.Min(6, attempt))));
        var jitter = TimeSpan.FromMilliseconds(Random.Shared.Next(0, 500));
        return exponential + jitter;
    }
}
