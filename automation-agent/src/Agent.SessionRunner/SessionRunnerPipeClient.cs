using System.Diagnostics;
using System.IO.Pipes;
using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Sessions;
using Biason.AutomationAgent.Protocol.Local;
using Biason.AutomationAgent.Protocol.Serialization;
using Microsoft.Extensions.Options;

namespace Biason.AutomationAgent.SessionRunner;

public sealed class SessionRunnerPipeClient : IAsyncDisposable
{
    private readonly SessionRunnerOptions _runnerOptions;
    private readonly LocalProtocolOptions _protocolOptions;
    private NamedPipeClientStream? _pipe;
    private StreamReader? _reader;
    private StreamWriter? _writer;
    private readonly SemaphoreSlim _sendLock = new(1, 1);

    public SessionRunnerPipeClient(
        IOptions<SessionRunnerOptions> runnerOptions,
        IOptions<LocalProtocolOptions> protocolOptions)
    {
        _runnerOptions = runnerOptions.Value;
        _protocolOptions = protocolOptions.Value;
    }

    public bool IsConnected => _pipe?.IsConnected == true;

    public async Task ConnectAsync(CancellationToken ct)
    {
        await DisposePipeAsync();
        _pipe = new NamedPipeClientStream(".", _runnerOptions.PipeName, PipeDirection.InOut, PipeOptions.Asynchronous);
        await _pipe.ConnectAsync(TimeSpan.FromSeconds(10), ct);
        _reader = new StreamReader(_pipe, leaveOpen: true);
        _writer = new StreamWriter(_pipe, leaveOpen: true) { AutoFlush = true };
    }

    public async Task<string> AuthenticateAndRegisterAsync(
        string instanceId,
        WindowsSession session,
        DesktopState desktop,
        string version,
        CancellationToken ct)
    {
        var processId = Environment.ProcessId;
        await SendAsync(new LocalProtocolEnvelope
        {
            MessageType = LocalMessageTypes.Hello,
            SessionRunnerInstanceId = instanceId,
            SessionId = session.SessionId,
            Payload = new SessionRunnerHelloPayload
            {
                InstanceId = instanceId,
                SessionId = session.SessionId,
                ProcessId = processId,
                Version = version
            }
        }, ct);

        var challengeEnvelope = await ReadAsync(ct);
        var challenge = ProtocolJson.ReadPayload<SessionRunnerChallengePayload>(challengeEnvelope.Payload)
            ?? throw new InvalidOperationException("Agent Service returned invalid challenge.");

        var response = LocalAuthentication.ChallengeResponse(challenge.Nonce, instanceId, session.SessionId, processId);
        await SendAsync(new LocalProtocolEnvelope
        {
            MessageType = LocalMessageTypes.Authenticate,
            SessionRunnerInstanceId = instanceId,
            SessionId = session.SessionId,
            CorrelationId = challengeEnvelope.MessageId,
            Payload = new SessionRunnerAuthenticatePayload
            {
                ChallengeId = challenge.ChallengeId,
                Response = response
            }
        }, ct);

        await SendAsync(new LocalProtocolEnvelope
        {
            MessageType = LocalMessageTypes.Register,
            SessionRunnerInstanceId = instanceId,
            SessionId = session.SessionId,
            Payload = new SessionRunnerRegisterPayload
            {
                InstanceId = instanceId,
                SessionId = session.SessionId,
                ProcessId = processId,
                Version = version,
                User = session.User,
                Domain = session.Domain,
                SessionType = session.Type,
                SessionState = session.State,
                Desktop = desktop
            }
        }, ct);

        var registeredEnvelope = await ReadAsync(ct);
        if (registeredEnvelope.MessageType == LocalMessageTypes.ProtocolError)
            throw new InvalidOperationException("Agent Service rejected Session Runner registration.");

        var registered = ProtocolJson.ReadPayload<SessionRunnerRegisteredPayload>(registeredEnvelope.Payload)
            ?? throw new InvalidOperationException("Agent Service returned invalid registration payload.");

        return registered.SessionToken;
    }

    public async Task SendHeartbeatAsync(string instanceId, int sessionId, string token, WindowsSessionState state, DesktopState desktop, CancellationToken ct)
    {
        await SendAsync(new LocalProtocolEnvelope
        {
            MessageType = LocalMessageTypes.Heartbeat,
            SessionRunnerInstanceId = instanceId,
            SessionId = sessionId,
            Token = token,
            Payload = new SessionRunnerHeartbeatPayload
            {
                SessionId = sessionId,
                ProcessId = Environment.ProcessId,
                SessionState = state,
                Desktop = desktop
            }
        }, ct);
    }

    public async Task<LocalProtocolEnvelope?> ReadNextAsync(CancellationToken ct)
    {
        if (_reader is null) throw new InvalidOperationException("Pipe is not connected.");
        var line = await _reader.ReadLineAsync(ct);
        if (line is null) return null;
        var (result, envelope) = LocalProtocolValidator.Parse(line, DateTime.UtcNow, _protocolOptions.MaximumMessageBytes, _protocolOptions.Version);
        if (!result.IsValid || envelope is null)
            throw new InvalidOperationException(result.Message ?? "Invalid local protocol message.");
        return envelope;
    }

    public async Task SendInteractiveStatusAsync(
        string instanceId,
        int sessionId,
        string token,
        string messageType,
        InteractiveExecutionStatusPayload payload,
        CancellationToken ct)
    {
        await SendAsync(new LocalProtocolEnvelope
        {
            MessageType = messageType,
            SessionRunnerInstanceId = instanceId,
            SessionId = sessionId,
            Token = token,
            Payload = payload
        }, ct);
    }

    public async Task SendStateChangedAsync(string instanceId, int sessionId, string token, string eventType, WindowsSessionState state, DesktopState desktop, CancellationToken ct)
    {
        await SendAsync(new LocalProtocolEnvelope
        {
            MessageType = LocalMessageTypes.SessionStateChanged,
            SessionRunnerInstanceId = instanceId,
            SessionId = sessionId,
            Token = token,
            Payload = new SessionStateChangedPayload
            {
                SessionId = sessionId,
                State = state,
                EventType = eventType,
                Desktop = desktop
            }
        }, ct);
    }

    public async Task SendStoppingAsync(string instanceId, int sessionId, string token, CancellationToken ct)
    {
        if (!IsConnected) return;
        await SendAsync(new LocalProtocolEnvelope
        {
            MessageType = LocalMessageTypes.Stopping,
            SessionRunnerInstanceId = instanceId,
            SessionId = sessionId,
            Token = token,
            Payload = new { process_id = Environment.ProcessId }
        }, ct);
    }

    private async Task SendAsync(LocalProtocolEnvelope envelope, CancellationToken ct)
    {
        if (_writer is null) throw new InvalidOperationException("Pipe is not connected.");
        await _sendLock.WaitAsync(ct);
        try
        {
            await _writer.WriteLineAsync(ProtocolJson.Serialize(envelope).AsMemory(), ct);
        }
        finally
        {
            _sendLock.Release();
        }
    }

    private async Task<LocalProtocolEnvelope> ReadAsync(CancellationToken ct)
    {
        if (_reader is null) throw new InvalidOperationException("Pipe is not connected.");
        var line = await _reader.ReadLineAsync(ct) ?? throw new EndOfStreamException("Pipe closed.");
        var (result, envelope) = LocalProtocolValidator.Parse(line, DateTime.UtcNow, _protocolOptions.MaximumMessageBytes, _protocolOptions.Version);
        if (!result.IsValid || envelope is null)
            throw new InvalidOperationException(result.Message ?? "Invalid local protocol message.");
        return envelope;
    }

    private async ValueTask DisposePipeAsync()
    {
        if (_writer is not null) await _writer.DisposeAsync();
        _reader?.Dispose();
        if (_pipe is not null) await _pipe.DisposeAsync();
        _writer = null;
        _reader = null;
        _pipe = null;
    }

    public async ValueTask DisposeAsync() => await DisposePipeAsync();
}
