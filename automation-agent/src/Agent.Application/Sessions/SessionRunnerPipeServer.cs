using System.IO.Pipes;
using System.Security.Cryptography;
using System.Collections.Concurrent;
using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Execution;
using Biason.AutomationAgent.Domain.Models.Interactive;
using Biason.AutomationAgent.Domain.Models.Sessions;
using Biason.AutomationAgent.Application.Messaging;
using Biason.AutomationAgent.Protocol.Local;
using Biason.AutomationAgent.Protocol.Messages;
using Biason.AutomationAgent.Protocol.Serialization;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using Microsoft.Win32.SafeHandles;
using System.Runtime.InteropServices;

namespace Biason.AutomationAgent.Application.Sessions;

public sealed class SessionRunnerPipeServer : BackgroundService
{
    private readonly ISessionRunnerRegistry _registry;
    private readonly ISessionRunnerProcessValidator _processValidator;
    private readonly ISessionRunnerConnectionRepository _connections;
    private readonly ISessionEventRepository _events;
    private readonly IInteractiveExecutionAssignmentRepository _interactiveAssignments;
    private readonly IInteractiveExecutionProcessRepository _interactiveProcesses;
    private readonly IExecutionEventRepository _executionEvents;
    private readonly OutboxMessagePublisher _outbox;
    private readonly IClock _clock;
    private readonly SessionRunnerOptions _runnerOptions;
    private readonly LocalProtocolOptions _protocolOptions;
    private readonly ILogger<SessionRunnerPipeServer> _logger;
    private int _activeConnections;
    private DateTime? _startedAtUtc;
    private string? _lastError;
    private NamedPipeServerStream? _listeningPipe;
    private readonly ConcurrentDictionary<string, ConnectedRunnerClient> _clients = new(StringComparer.Ordinal);
    private readonly ConcurrentDictionary<string, TaskCompletionSource<InteractiveRunnerResult>> _pendingExecutions = new(StringComparer.Ordinal);

    public SessionRunnerPipeServer(
        ISessionRunnerRegistry registry,
        ISessionRunnerProcessValidator processValidator,
        ISessionRunnerConnectionRepository connections,
        ISessionEventRepository events,
        IInteractiveExecutionAssignmentRepository interactiveAssignments,
        IInteractiveExecutionProcessRepository interactiveProcesses,
        IExecutionEventRepository executionEvents,
        OutboxMessagePublisher outbox,
        IClock clock,
        IOptions<SessionRunnerOptions> runnerOptions,
        IOptions<LocalProtocolOptions> protocolOptions,
        ILogger<SessionRunnerPipeServer> logger)
    {
        _registry = registry;
        _processValidator = processValidator;
        _connections = connections;
        _events = events;
        _interactiveAssignments = interactiveAssignments;
        _interactiveProcesses = interactiveProcesses;
        _executionEvents = executionEvents;
        _outbox = outbox;
        _clock = clock;
        _runnerOptions = runnerOptions.Value;
        _protocolOptions = protocolOptions.Value;
        _logger = logger;
    }

    public object GetStatus() => new
    {
        pipe_name = _runnerOptions.PipeName,
        started_at_utc = _startedAtUtc,
        active_connections = _activeConnections,
        acl_mode = "current_user_only",
        last_error = _lastError,
        connected_runners = _clients.Keys.OrderBy(k => k, StringComparer.Ordinal).ToArray(),
        pending_interactive_executions = _pendingExecutions.Count
    };

    public async Task<InteractiveRunnerResult> StartInteractiveExecutionAsync(
        string sessionRunnerInstanceId,
        int sessionId,
        InteractiveExecutionStartPayload payload,
        TimeSpan timeout,
        CancellationToken ct = default)
    {
        if (!_clients.TryGetValue(sessionRunnerInstanceId, out var client))
            return InteractiveRunnerResult.Failed("SESSION_RUNNER_NOT_CONNECTED", $"Session Runner {sessionRunnerInstanceId} is not connected.");

        var key = PendingKey(payload.ExecutionId, payload.ExecutionAttemptId);
        var tcs = new TaskCompletionSource<InteractiveRunnerResult>(TaskCreationOptions.RunContinuationsAsynchronously);
        if (!_pendingExecutions.TryAdd(key, tcs))
            return InteractiveRunnerResult.Failed("EXECUTION_ALREADY_RUNNING", $"Attempt {payload.ExecutionAttemptId} is already pending.");

        try
        {
            await client.SendAsync(new LocalProtocolEnvelope
            {
                MessageType = LocalMessageTypes.InteractiveExecutionStart,
                SessionRunnerInstanceId = sessionRunnerInstanceId,
                SessionId = sessionId,
                SentAt = _clock.UtcNow,
                Payload = payload
            }, ct);

            return await tcs.Task.WaitAsync(timeout, ct);
        }
        catch (TimeoutException)
        {
            return InteractiveRunnerResult.Failed("INTERACTIVE_EXECUTION_TIMEOUT", $"Attempt {payload.ExecutionAttemptId} did not finish before the local timeout.");
        }
        catch (OperationCanceledException)
        {
            return InteractiveRunnerResult.CancelledResult("cancelled by Agent Service");
        }
        finally
        {
            _pendingExecutions.TryRemove(key, out _);
        }
    }

    public async Task<bool> CancelInteractiveExecutionAsync(
        string sessionRunnerInstanceId,
        int sessionId,
        InteractiveExecutionCancelPayload payload,
        CancellationToken ct = default)
    {
        if (!_clients.TryGetValue(sessionRunnerInstanceId, out var client))
            return false;

        await client.SendAsync(new LocalProtocolEnvelope
        {
            MessageType = LocalMessageTypes.InteractiveExecutionCancel,
            SessionRunnerInstanceId = sessionRunnerInstanceId,
            SessionId = sessionId,
            SentAt = _clock.UtcNow,
            Payload = payload
        }, ct);
        return true;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        _startedAtUtc = _clock.UtcNow;
        _logger.LogInformation("NAMED_PIPE_STARTED {PipeName}", _runnerOptions.PipeName);

        while (!stoppingToken.IsCancellationRequested)
        {
            NamedPipeServerStream? pipe = null;
            try
            {
                pipe = CreatePipe();
                _listeningPipe = pipe;
                await pipe.WaitForConnectionAsync(stoppingToken);
                _listeningPipe = null;
                Interlocked.Increment(ref _activeConnections);
                _ = Task.Run(() => HandleClientAsync(pipe, stoppingToken), stoppingToken);
                pipe = null;
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
            {
                pipe?.Dispose();
                _listeningPipe = null;
                break;
            }
            catch (Exception ex)
            {
                pipe?.Dispose();
                _listeningPipe = null;
                _lastError = ex.Message;
                _logger.LogWarning(ex, "NAMED_PIPE_ERROR Session Runner pipe accept failed.");
                try { await Task.Delay(TimeSpan.FromSeconds(1), stoppingToken); }
                catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested) { break; }
            }
        }
    }

    public override async Task StopAsync(CancellationToken cancellationToken)
    {
        try { _listeningPipe?.Dispose(); }
        catch { /* best effort */ }
        await base.StopAsync(cancellationToken);
    }

    private NamedPipeServerStream CreatePipe()
    {
        try
        {
            return new NamedPipeServerStream(
                _runnerOptions.PipeName,
                PipeDirection.InOut,
                NamedPipeServerStream.MaxAllowedServerInstances,
                PipeTransmissionMode.Byte,
                PipeOptions.Asynchronous | PipeOptions.CurrentUserOnly);
        }
        catch (PlatformNotSupportedException)
        {
            return new NamedPipeServerStream(
                _runnerOptions.PipeName,
                PipeDirection.InOut,
                NamedPipeServerStream.MaxAllowedServerInstances,
                PipeTransmissionMode.Byte,
                PipeOptions.Asynchronous);
        }
    }

    private async Task HandleClientAsync(NamedPipeServerStream pipe, CancellationToken serverToken)
    {
        string? instanceId = null;
        long? connectionId = null;
        try
        {
            await using (pipe)
            using (var reader = new StreamReader(pipe, leaveOpen: true))
            await using (var writer = new StreamWriter(pipe, leaveOpen: true) { AutoFlush = true })
            {
                _logger.LogInformation("NAMED_PIPE_CLIENT_CONNECTED Session Runner pipe client connected.");

                var helloEnvelope = await ReadEnvelopeAsync(reader, serverToken);
                if (helloEnvelope?.MessageType != LocalMessageTypes.Hello)
                {
                    await SendErrorAsync(writer, null, LocalProtocolErrors.MalformedJson, "Expected session_runner.hello.", serverToken);
                    return;
                }

                var hello = ProtocolJson.ReadPayload<SessionRunnerHelloPayload>(helloEnvelope.Payload);
                if (hello is null)
                {
                    await SendErrorAsync(writer, helloEnvelope.MessageId, LocalProtocolErrors.MalformedJson, "Invalid hello payload.", serverToken);
                    return;
                }

                instanceId = hello.InstanceId;
                var actualPid = TryGetClientProcessId(pipe);
                var validation = await _processValidator.ValidateAsync(actualPid, hello.ProcessId, hello.SessionId, serverToken);
                if (!validation.IsValid)
                {
                    _logger.LogWarning("NAMED_PIPE_CLIENT_REJECTED {Code}", validation.ErrorCode);
                    await SendErrorAsync(writer, helloEnvelope.MessageId, validation.ErrorCode ?? LocalProtocolErrors.InvalidProcess, validation.Message ?? "Invalid Session Runner process.", serverToken);
                    return;
                }

                connectionId = await _connections.AddAsync(new SessionRunnerConnectionRecord
                {
                    SessionRunnerInstanceId = hello.InstanceId,
                    SessionId = hello.SessionId,
                    ConnectedAtUtc = _clock.UtcNow,
                    RemoteProcessId = actualPid,
                    ProtocolVersion = helloEnvelope.ProtocolVersion,
                    Status = "connected"
                }, serverToken);

                var challenge = NewChallenge();
                await SendAsync(writer, new LocalProtocolEnvelope
                {
                    MessageType = LocalMessageTypes.Challenge,
                    CorrelationId = helloEnvelope.MessageId,
                    SessionRunnerInstanceId = hello.InstanceId,
                    SessionId = hello.SessionId,
                    SentAt = _clock.UtcNow,
                    Payload = challenge.Payload
                }, serverToken);

                var authEnvelope = await ReadEnvelopeAsync(reader, serverToken);
                var auth = ProtocolJson.ReadPayload<SessionRunnerAuthenticatePayload>(authEnvelope?.Payload);
                if (authEnvelope?.MessageType != LocalMessageTypes.Authenticate || auth is null)
                {
                    await SendErrorAsync(writer, authEnvelope?.MessageId, LocalProtocolErrors.InvalidChallenge, "Expected valid session_runner.authenticate.", serverToken);
                    return;
                }

                if (!string.Equals(auth.ChallengeId, challenge.ChallengeId, StringComparison.Ordinal))
                {
                    await SendErrorAsync(writer, authEnvelope.MessageId, LocalProtocolErrors.InvalidChallenge, "Challenge id rejected.", serverToken);
                    return;
                }

                if (_clock.UtcNow > challenge.ExpiresAtUtc)
                {
                    await SendErrorAsync(writer, authEnvelope.MessageId, LocalProtocolErrors.ExpiredChallenge, "Challenge expired.", serverToken);
                    return;
                }

                var expected = LocalAuthentication.ChallengeResponse(challenge.Nonce, hello.InstanceId, hello.SessionId, hello.ProcessId);
                if (!string.Equals(expected, auth.Response, StringComparison.Ordinal))
                {
                    await SendErrorAsync(writer, authEnvelope.MessageId, LocalProtocolErrors.InvalidChallenge, "Challenge response rejected.", serverToken);
                    return;
                }

                await _connections.MarkAuthenticatedAsync(connectionId.Value, _clock.UtcNow, serverToken);
                _logger.LogInformation("SESSION_RUNNER_AUTHENTICATED {InstanceId}", hello.InstanceId);

                var registerEnvelope = await ReadEnvelopeAsync(reader, serverToken);
                var register = ProtocolJson.ReadPayload<SessionRunnerRegisterPayload>(registerEnvelope?.Payload);
                if (registerEnvelope?.MessageType != LocalMessageTypes.Register || register is null)
                {
                    await SendErrorAsync(writer, registerEnvelope?.MessageId, LocalProtocolErrors.MalformedJson, "Expected valid session_runner.register.", serverToken);
                    return;
                }

                if (register.InstanceId != hello.InstanceId || register.SessionId != hello.SessionId || register.ProcessId != hello.ProcessId)
                {
                    await SendErrorAsync(writer, registerEnvelope.MessageId, LocalProtocolErrors.SessionIdMismatch, "Register payload does not match authenticated hello.", serverToken);
                    return;
                }

                var tokenExpires = _clock.UtcNow.AddMinutes(_protocolOptions.SessionTokenExpirationMinutes);
                var token = _registry.IssueSessionToken(register.InstanceId, register.SessionId, register.ProcessId, tokenExpires, out var fingerprint);

                await _registry.RegisterAsync(new SessionRunnerRecord
                {
                    InstanceId = register.InstanceId,
                    SessionId = register.SessionId,
                    UserName = register.User,
                    DomainName = register.Domain,
                    SessionType = register.SessionType,
                    ProcessId = register.ProcessId,
                    Version = register.Version,
                    Desktop = register.Desktop,
                    State = SessionRunnerConnectionState.Connected,
                    RegisteredAtUtc = _clock.UtcNow,
                    LastHeartbeatAtUtc = _clock.UtcNow,
                    SessionTokenFingerprint = fingerprint,
                    SessionTokenExpiresAtUtc = tokenExpires
                }, serverToken);
                await _registry.RecordHeartbeatAsync(register.InstanceId, _clock.UtcNow, register.Desktop, serverToken);

                await SendAsync(writer, new LocalProtocolEnvelope
                {
                    MessageType = LocalMessageTypes.Registered,
                    CorrelationId = registerEnvelope.MessageId,
                    SessionRunnerInstanceId = register.InstanceId,
                    SessionId = register.SessionId,
                    SentAt = _clock.UtcNow,
                    Payload = new SessionRunnerRegisteredPayload
                    {
                        SessionToken = token,
                        ExpiresAtUtc = tokenExpires,
                        HeartbeatIntervalSeconds = _runnerOptions.HeartbeatIntervalSeconds
                    }
                }, serverToken);
                _logger.LogInformation("SESSION_RUNNER_REGISTERED {InstanceId}", register.InstanceId);

                _clients[register.InstanceId] = new ConnectedRunnerClient(register.InstanceId, register.SessionId, writer, _clock);
                await PumpAuthenticatedAsync(reader, writer, register, serverToken);
            }
        }
        catch (OperationCanceledException) when (serverToken.IsCancellationRequested)
        {
            // service shutdown
        }
        catch (Exception ex)
        {
            _lastError = ex.Message;
            _logger.LogWarning(ex, "NAMED_PIPE_ERROR Session Runner client handling failed.");
        }
        finally
        {
            Interlocked.Decrement(ref _activeConnections);
            if (instanceId is not null)
                _clients.TryRemove(instanceId, out _);
            if (instanceId is not null)
                await _registry.MarkDisconnectedAsync(instanceId, "pipe_disconnected", CancellationToken.None);
            if (connectionId is not null)
                await _connections.MarkDisconnectedAsync(connectionId.Value, _clock.UtcNow, "pipe_disconnected", CancellationToken.None);
        }
    }

    private async Task PumpAuthenticatedAsync(
        StreamReader reader,
        StreamWriter writer,
        SessionRunnerRegisterPayload register,
        CancellationToken ct)
    {
        while (!ct.IsCancellationRequested)
        {
            var envelope = await ReadEnvelopeAsync(reader, ct);
            if (envelope is null) return;

            if (!_registry.TryValidateSessionToken(envelope.Token ?? "", register.InstanceId, register.SessionId, register.ProcessId, _clock.UtcNow))
            {
                await SendErrorAsync(writer, envelope.MessageId, LocalProtocolErrors.InvalidToken, "Invalid or expired session token.", ct);
                continue;
            }

            switch (envelope.MessageType)
            {
                case LocalMessageTypes.Heartbeat:
                    var heartbeat = ProtocolJson.ReadPayload<SessionRunnerHeartbeatPayload>(envelope.Payload);
                    if (heartbeat is not null)
                    {
                        await _registry.RecordHeartbeatAsync(register.InstanceId, _clock.UtcNow, heartbeat.Desktop, ct);
                        await SendAsync(writer, new LocalProtocolEnvelope
                        {
                            MessageType = LocalMessageTypes.HeartbeatAck,
                            CorrelationId = envelope.MessageId,
                            SessionRunnerInstanceId = register.InstanceId,
                            SessionId = register.SessionId,
                            SentAt = _clock.UtcNow,
                            Payload = new { ok = true }
                        }, ct);
                    }
                    break;

                case LocalMessageTypes.SessionStateChanged:
                case LocalMessageTypes.DesktopStateChanged:
                    await _events.AddAsync(new SessionEventRecord
                    {
                        SessionId = envelope.SessionId,
                        SessionRunnerInstanceId = envelope.SessionRunnerInstanceId,
                        EventType = envelope.MessageType == LocalMessageTypes.SessionStateChanged
                            ? "session.state_changed"
                            : "desktop.state_changed",
                        DetailJson = ProtocolJson.Serialize(envelope.Payload),
                        OccurredAtUtc = _clock.UtcNow
                    }, ct);
                    break;

                case LocalMessageTypes.Stopping:
                    await _registry.MarkDisconnectedAsync(register.InstanceId, "runner_stopping", ct);
                    return;

                case LocalMessageTypes.InteractiveExecutionStarted:
                case LocalMessageTypes.InteractiveExecutionLog:
                case LocalMessageTypes.InteractiveExecutionProgress:
                case LocalMessageTypes.InteractiveExecutionMetric:
                case LocalMessageTypes.InteractiveExecutionArtifact:
                case LocalMessageTypes.InteractiveExecutionCompleted:
                case LocalMessageTypes.InteractiveExecutionFailed:
                case LocalMessageTypes.InteractiveExecutionCancelled:
                case LocalMessageTypes.InteractiveExecutionHeartbeat:
                case LocalMessageTypes.InteractiveAutomationEvent:
                    await RecordInteractiveExecutionMessageAsync(envelope, ct);
                    break;
            }
        }
    }

    private async Task RecordInteractiveExecutionMessageAsync(LocalProtocolEnvelope envelope, CancellationToken ct)
    {
        var status = ProtocolJson.ReadPayload<InteractiveExecutionStatusPayload>(envelope.Payload);
        if (status is null || string.IsNullOrWhiteSpace(status.ExecutionId) || string.IsNullOrWhiteSpace(status.ExecutionAttemptId))
            return;

        var now = _clock.UtcNow;
        var portalType = MapPortalEventType(envelope.MessageType);
        var eventType = envelope.MessageType.Replace("interactive.", "", StringComparison.Ordinal);
        var dataJson = ProtocolJson.Serialize(envelope.Payload);

        await _executionEvents.SaveAsync(new ExecutionEvent
        {
            ExecutionId = status.ExecutionId,
            AttemptId = status.ExecutionAttemptId,
            EventType = eventType,
            Message = status.Message,
            DataJson = dataJson,
            OccurredAtUtc = now
        }, ct);

        if (envelope.MessageType == LocalMessageTypes.InteractiveExecutionStarted && status.ProcessId.HasValue)
        {
            await _interactiveAssignments.MarkStartedAsync(status.ExecutionId, status.ExecutionAttemptId, status.ProcessId.Value, now, ct);
            await _interactiveProcesses.AddAsync(new InteractiveExecutionProcessRecord
            {
                ExecutionId = status.ExecutionId,
                AttemptId = status.ExecutionAttemptId,
                ProcessId = status.ProcessId.Value,
                SessionId = envelope.SessionId,
                ObservedAtUtc = now,
                StartedAtUtc = now,
                Kind = "execution_host",
                Status = "running"
            }, ct);
        }

        if (envelope.MessageType is LocalMessageTypes.InteractiveExecutionCompleted or
            LocalMessageTypes.InteractiveExecutionFailed or
            LocalMessageTypes.InteractiveExecutionCancelled)
        {
            var resultStatus = envelope.MessageType switch
            {
                LocalMessageTypes.InteractiveExecutionCompleted => InteractiveExecutionStatus.Completed,
                LocalMessageTypes.InteractiveExecutionCancelled => InteractiveExecutionStatus.Cancelled,
                _ => InteractiveExecutionStatus.Failed
            };

            await _interactiveAssignments.MarkCompletedAsync(
                status.ExecutionId,
                status.ExecutionAttemptId,
                resultStatus,
                status.ExitCode,
                now,
                status.ErrorCode,
                status.Message,
                ct);

            if (status.ProcessId.HasValue)
                await _interactiveProcesses.MarkExitedAsync(status.ExecutionId, status.ExecutionAttemptId, status.ProcessId.Value, now, status.ExitCode, ct);

            CompletePending(status, resultStatus);
        }

        await _outbox.EnqueueAsync(
            portalType,
            status.Payload ?? envelope.Payload,
            correlationId: envelope.CorrelationId,
            causationId: envelope.MessageId,
            executionId: status.ExecutionId,
            executionAttemptId: status.ExecutionAttemptId,
            ct: ct);
    }

    private void CompletePending(InteractiveExecutionStatusPayload status, InteractiveExecutionStatus resultStatus)
    {
        var key = PendingKey(status.ExecutionId, status.ExecutionAttemptId);
        if (!_pendingExecutions.TryGetValue(key, out var tcs))
            return;

        if (resultStatus == InteractiveExecutionStatus.Completed)
            tcs.TrySetResult(InteractiveRunnerResult.Completed(status.ExitCode ?? 0));
        else if (resultStatus == InteractiveExecutionStatus.Cancelled)
            tcs.TrySetResult(InteractiveRunnerResult.CancelledResult(status.Message ?? "cancelled"));
        else
            tcs.TrySetResult(InteractiveRunnerResult.Failed(status.ErrorCode ?? "INTERACTIVE_EXECUTION_FAILED", status.Message ?? "Interactive execution failed.", status.ExitCode));
    }

    private static string MapPortalEventType(string localType) => localType switch
    {
        LocalMessageTypes.InteractiveExecutionStarted => PortalMessageTypes.ExecutionStarted,
        LocalMessageTypes.InteractiveExecutionLog => PortalMessageTypes.ExecutionLog,
        LocalMessageTypes.InteractiveExecutionProgress => PortalMessageTypes.ExecutionProgress,
        LocalMessageTypes.InteractiveExecutionMetric => PortalMessageTypes.ExecutionMetric,
        LocalMessageTypes.InteractiveExecutionArtifact => PortalMessageTypes.ExecutionArtifactCreated,
        LocalMessageTypes.InteractiveExecutionCompleted => PortalMessageTypes.ExecutionCompleted,
        LocalMessageTypes.InteractiveExecutionFailed => PortalMessageTypes.ExecutionFailed,
        LocalMessageTypes.InteractiveExecutionCancelled => PortalMessageTypes.ExecutionCancelled,
        LocalMessageTypes.InteractiveExecutionHeartbeat => PortalMessageTypes.ExecutionMetric,
        LocalMessageTypes.InteractiveAutomationEvent => PortalMessageTypes.AutomationEvent,
        _ => PortalMessageTypes.ExecutionLog
    };

    private static string PendingKey(string executionId, string attemptId) => $"{executionId}|{attemptId}";

    private async Task<LocalProtocolEnvelope?> ReadEnvelopeAsync(StreamReader reader, CancellationToken ct)
    {
        var line = await reader.ReadLineAsync(ct);
        if (line is null) return null;
        var (result, envelope) = LocalProtocolValidator.Parse(line, _clock.UtcNow, _protocolOptions.MaximumMessageBytes, _protocolOptions.Version);
        return result.IsValid ? envelope : null;
    }

    private async Task SendErrorAsync(StreamWriter writer, string? correlationId, string errorCode, string message, CancellationToken ct)
    {
        await SendAsync(writer, new LocalProtocolEnvelope
        {
            MessageType = LocalMessageTypes.ProtocolError,
            CorrelationId = correlationId,
            SentAt = _clock.UtcNow,
            Payload = new LocalProtocolErrorPayload { ErrorCode = errorCode, ErrorMessage = message }
        }, ct);
    }

    private static async Task SendAsync(StreamWriter writer, LocalProtocolEnvelope envelope, CancellationToken ct)
    {
        await writer.WriteLineAsync(ProtocolJson.Serialize(envelope).AsMemory(), ct);
    }

    private ChallengeState NewChallenge()
    {
        var bytes = RandomNumberGenerator.GetBytes(32);
        var nonce = Convert.ToBase64String(bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_');
        return new ChallengeState(
            $"challenge_{Guid.NewGuid():N}",
            nonce,
            _clock.UtcNow.AddSeconds(_protocolOptions.ChallengeExpirationSeconds));
    }

    private static int TryGetClientProcessId(NamedPipeServerStream pipe)
    {
        try
        {
            if (!OperatingSystem.IsWindows()) return -1;
            return GetNamedPipeClientProcessId(pipe.SafePipeHandle, out var processId) ? unchecked((int)processId) : -1;
        }
        catch
        {
            return -1;
        }
    }

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool GetNamedPipeClientProcessId(SafePipeHandle pipe, out uint clientProcessId);

    private sealed record ChallengeState(string ChallengeId, string Nonce, DateTime ExpiresAtUtc)
    {
        public SessionRunnerChallengePayload Payload => new()
        {
            ChallengeId = ChallengeId,
            Nonce = Nonce,
            ExpiresAtUtc = ExpiresAtUtc
        };
    }

    private sealed class ConnectedRunnerClient
    {
        private readonly StreamWriter _writer;
        private readonly IClock _clock;
        private readonly SemaphoreSlim _sendLock = new(1, 1);

        public ConnectedRunnerClient(string instanceId, int sessionId, StreamWriter writer, IClock clock)
        {
            InstanceId = instanceId;
            SessionId = sessionId;
            _writer = writer;
            _clock = clock;
        }

        public string InstanceId { get; }
        public int SessionId { get; }

        public async Task SendAsync(LocalProtocolEnvelope envelope, CancellationToken ct)
        {
            await _sendLock.WaitAsync(ct);
            try
            {
                var outgoing = new LocalProtocolEnvelope
                {
                    ProtocolVersion = envelope.ProtocolVersion,
                    MessageId = envelope.MessageId,
                    MessageType = envelope.MessageType,
                    SentAt = envelope.SentAt == default ? _clock.UtcNow : envelope.SentAt,
                    SessionRunnerInstanceId = envelope.SessionRunnerInstanceId ?? InstanceId,
                    SessionId = envelope.SessionId ?? SessionId,
                    CorrelationId = envelope.CorrelationId,
                    Token = envelope.Token,
                    Payload = envelope.Payload
                };
                await _writer.WriteLineAsync(ProtocolJson.Serialize(outgoing).AsMemory(), ct);
            }
            finally
            {
                _sendLock.Release();
            }
        }
    }
}

public sealed class InteractiveRunnerResult
{
    private InteractiveRunnerResult(bool success, bool cancelled, int? exitCode, string? errorCode, string? errorMessage)
    {
        Success = success;
        Cancelled = cancelled;
        ExitCode = exitCode;
        ErrorCode = errorCode;
        ErrorMessage = errorMessage;
    }

    public bool Success { get; }
    public bool Cancelled { get; }
    public int? ExitCode { get; }
    public string? ErrorCode { get; }
    public string? ErrorMessage { get; }

    public static InteractiveRunnerResult Completed(int exitCode) => new(true, false, exitCode, null, null);
    public static InteractiveRunnerResult CancelledResult(string message) => new(false, true, null, null, message);
    public static InteractiveRunnerResult Failed(string code, string message, int? exitCode = null) => new(false, false, exitCode, code, message);
}
