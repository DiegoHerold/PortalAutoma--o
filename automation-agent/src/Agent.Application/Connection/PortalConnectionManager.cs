using System.Threading.Channels;
using System.Text.Json;
using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Connections;
using Biason.AutomationAgent.Domain.StateMachines;
using Biason.AutomationAgent.Protocol.Envelope;
using Biason.AutomationAgent.Protocol.Messages;
using Biason.AutomationAgent.Protocol.Serialization;
using Biason.AutomationAgent.Protocol.Validation;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace Biason.AutomationAgent.Application.Connection;

/// <summary>
/// Conexão WebSocket única e persistente com o Portal.
///
/// Uma instância por processo (registrada como singleton). <see cref="RunAsync"/> só
/// pode estar ativo uma vez por instância — chamar de novo enquanto já roda é um erro
/// de programação, não uma forma de abrir uma segunda conexão (websocket-single-connection).
///
/// Não é responsável por garantir entrega at-least-once: isso é do Outbox (Incremento 3),
/// que persiste antes de chamar <see cref="TrySendAsync"/>. Esta classe só garante que,
/// enquanto a conexão está operacional, uma mensagem enfileirada é enviada em ordem.
/// </summary>
public sealed class PortalConnectionManager : IPortalConnectionManager
{
    private readonly IWebSocketTransportFactory _transportFactory;
    private readonly IAgentIdentityService _identity;
    private readonly IAgentCredentialStore _credentials;
    private readonly IConnectionStateRepository _stateRepo;
    private readonly IClock _clock;
    private readonly PortalOptions _options;
    private readonly AgentOptions _agentOptions;
    private readonly ILogger<PortalConnectionManager> _logger;

    private readonly string _connectionId = $"conn_{Guid.NewGuid():N}";
    private readonly ConnectionBackoffCalculator _backoff;
    private readonly SemaphoreSlim _runGate = new(1, 1);
    private readonly SemaphoreSlim _stateLock = new(1, 1);

    private ConnectionState _state = ConnectionState.Disconnected;
    private DateTime? _connectedAtUtc;
    private DateTime? _disconnectedAtUtc;
    private DateTime? _lastMessageAtUtc;
    private DateTime? _lastPongAtUtc;
    private string? _disconnectReason;
    private int _reconnectAttempt;
    private volatile bool _running;
    private volatile bool _disabledByRequest;
    private CancellationTokenSource? _wakeSignal;

    public PortalConnectionManager(
        IWebSocketTransportFactory transportFactory,
        IAgentIdentityService identity,
        IAgentCredentialStore credentials,
        IConnectionStateRepository stateRepo,
        IClock clock,
        IOptions<PortalOptions> options,
        IOptions<AgentOptions> agentOptions,
        ILogger<PortalConnectionManager> logger)
    {
        _transportFactory = transportFactory;
        _identity = identity;
        _credentials = credentials;
        _stateRepo = stateRepo;
        _clock = clock;
        _options = options.Value;
        _agentOptions = agentOptions.Value;
        _logger = logger;

        _backoff = new ConnectionBackoffCalculator(
            TimeSpan.FromSeconds(_options.ReconnectInitialSeconds),
            TimeSpan.FromSeconds(_options.ReconnectMaximumSeconds));
    }

    public PortalConnectionManager(
        IWebSocketTransportFactory transportFactory,
        IAgentIdentityService identity,
        IAgentCredentialStore credentials,
        IConnectionStateRepository stateRepo,
        IClock clock,
        IOptions<PortalOptions> options,
        ILogger<PortalConnectionManager> logger)
        : this(
            transportFactory,
            identity,
            credentials,
            stateRepo,
            clock,
            options,
            Options.Create(new AgentOptions()),
            logger)
    {
    }

    public ConnectionState CurrentState => _state;

    /// <summary>True enquanto <see cref="RunAsync"/> está ativo nesta instância. Diagnóstico/teste.</summary>
    public bool IsRunning => _running;

    public event Func<ConnectionState, ConnectionState, Task>? StateChanged;
    public event Func<InboundPortalMessage, Task>? MessageReceived;

    public async Task RunAsync(CancellationToken ct)
    {
        if (!await _runGate.WaitAsync(0, ct))
            throw new InvalidOperationException(
                "PortalConnectionManager.RunAsync já está em execução nesta instância. " +
                "Uma única conexão por Agent — não chame RunAsync uma segunda vez.");

        try
        {
            _running = true;
            await MainLoopAsync(ct);
        }
        finally
        {
            _running = false;
            _runGate.Release();
        }
    }

    private async Task MainLoopAsync(CancellationToken ct)
    {
        while (!ct.IsCancellationRequested)
        {
            if (_disabledByRequest)
            {
                await TransitionAsync(ConnectionState.Disabled, "disabled_by_request", null, ct);
                await WaitForWakeSignalAsync(ct);
                if (ct.IsCancellationRequested) break;
                await TransitionAsync(ConnectionState.Disconnected, "re_enabled", null, ct);
                continue;
            }

            if (!_options.Enabled)
            {
                await TransitionAsync(ConnectionState.Disabled, "portal_integration_disabled", null, ct);
                return;
            }

            // TryConnectAndPumpAsync (e HandleDisconnectAsync, chamado por ele) são os
            // únicos donos das transições de estado desta conexão — o loop principal só
            // decide QUANDO tentar de novo, não PARA QUAL estado ir. Isso evita o bug de
            // tentar "Disconnected -> Reconnecting" (transição inválida: "reconectando"
            // só faz sentido depois de ter conectado ao menos uma vez).
            var connected = await TryConnectAndPumpAsync(ct);

            if (ct.IsCancellationRequested)
                break;

            if (!connected)
            {
                _reconnectAttempt++;
                var delay = _backoff.NextDelay(_reconnectAttempt);

                _logger.LogWarning(
                    "Falha ao conectar ao Portal (tentativa {Attempt}). Nova tentativa em {Delay:F1}s.",
                    _reconnectAttempt, delay.TotalSeconds);

                try { await Task.Delay(delay, ct); }
                catch (OperationCanceledException) { break; }
            }
            else
            {
                // Conexão caiu depois de ter funcionado: reseta o contador de tentativas
                // (queda após sucesso não deve herdar o backoff acumulado de antes). O
                // primeiro retry após uma queda é imediato — só passa a ter backoff se
                // esse retry também falhar.
                _reconnectAttempt = 0;
            }
        }

        if (!ct.IsCancellationRequested)
            return;

        await TransitionAsync(ConnectionState.Disconnected, "shutdown", null, CancellationToken.None);
    }

    /// <summary>Conecta, autentica e bombeia mensagens até a conexão cair ou ser cancelada.</summary>
    private async Task<bool> TryConnectAndPumpAsync(CancellationToken ct)
    {
        // Transiciona para Connecting sempre primeiro — de Disconnected, Reconnecting ou
        // Disabled->Disconnected->Connecting, é sempre uma transição válida na tabela.
        var identity = await _identity.GetIdentityAsync(ct);
        var credential = await _credentials.GetAsync(ct);

        if (identity is null || !identity.IsRegistered || credential is null)
        {
            _logger.LogDebug("Agent ainda não registrado; adiando conexão WebSocket.");
            await TransitionAsync(ConnectionState.Disconnected, "not_registered", null, ct);
            return false;
        }

        // Only enter Connecting once the Agent has enough local identity
        // material to open a real socket.
        await TransitionAsync(ConnectionState.Connecting, "starting_connect", null, ct);

        await using var transport = _transportFactory.Create();
        var uri = BuildConnectUri(identity.AgentId!, identity.InstallationId);
        var headers = new Dictionary<string, string> { ["Authorization"] = $"Bearer {credential.Value}" };

        await TransitionAsync(ConnectionState.Authenticating, "handshake", null, ct);

        try
        {
            await transport.ConnectAsync(uri, headers, TimeSpan.FromSeconds(_options.ConnectionTimeoutSeconds), ct);
            if (!await CompleteGatewayHandshakeAsync(transport, identity.AgentId!, identity.InstanceId, ct))
            {
                await TransitionAsync(ConnectionState.Disconnected, "handshake_failed", "Portal did not complete agent.connect.", CancellationToken.None);
                return false;
            }
        }
        catch (OperationCanceledException) when (ct.IsCancellationRequested)
        {
            throw;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Falha no handshake WebSocket com o Portal.");
            await TransitionAsync(ConnectionState.Disconnected, "handshake_failed", ex.Message, CancellationToken.None);
            return false;
        }

        await _credentials.TouchLastUsedAsync(ct);

        var now = _clock.UtcNow;
        _connectedAtUtc = now;
        _disconnectedAtUtc = null;
        _lastMessageAtUtc = now;
        _lastPongAtUtc = now;
        await TransitionAsync(ConnectionState.Connected, "connected", null, ct);
        _logger.LogInformation("Conectado ao Portal ({Endpoint}).", _options.WebSocketUrl);

        var outbound = Channel.CreateBounded<string>(new BoundedChannelOptions(1000)
        {
            FullMode = BoundedChannelFullMode.Wait,
            SingleReader = true,
            SingleWriter = false
        });

        lock (_lock) { _outbound = outbound; }

        using var pumpCts = CancellationTokenSource.CreateLinkedTokenSource(ct);

        var sendTask = SendLoopAsync(transport, outbound.Reader, pumpCts.Token);
        var receiveTask = ReceiveLoopAsync(transport, identity.AgentId!, pumpCts.Token);
        var watchdogTask = WatchdogLoopAsync(pumpCts.Token);

        // A conexão "cai" quando qualquer um dos três laços termina — cancela os outros dois.
        var finished = await Task.WhenAny(sendTask, receiveTask, watchdogTask);
        pumpCts.Cancel();

        lock (_lock) { _outbound = null; }
        outbound.Writer.TryComplete();

        await SafeAwaitAsync(sendTask);
        await SafeAwaitAsync(receiveTask);
        await SafeAwaitAsync(watchdogTask);

        var reason = finished == watchdogTask ? "stale_connection" : "socket_closed";
        await HandleDisconnectAsync(transport, reason, ct);

        // Sucesso = chegamos a ficar Connected, mesmo que tenha caído depois.
        return true;
    }

    private async Task<bool> CompleteGatewayHandshakeAsync(
        IWebSocketTransport transport,
        string agentId,
        string agentInstanceId,
        CancellationToken ct)
    {
        using var handshakeCts = CancellationTokenSource.CreateLinkedTokenSource(ct);
        handshakeCts.CancelAfter(TimeSpan.FromSeconds(_options.ConnectionTimeoutSeconds));

        var handshake = new
        {
            message_type = "agent.connect",
            payload = new
            {
                agent_id = agentId,
                agent_instance_id = agentInstanceId,
                agent_version = _agentOptions.Version,
                supported_protocol_versions = new[] { ProtocolConstants.CurrentVersion }
            }
        };

        await transport.SendTextAsync(ProtocolJson.Serialize(handshake), handshakeCts.Token);

        while (!handshakeCts.Token.IsCancellationRequested)
        {
            var received = await transport.ReceiveAsync(handshakeCts.Token);
            if (received.Kind == TransportMessageKind.Closed)
            {
                _logger.LogWarning("Portal closed the socket during handshake: {Reason}", received.CloseReason);
                return false;
            }

            if (received.Kind == TransportMessageKind.Error)
            {
                _logger.LogWarning(received.Error, "Portal socket failed during handshake.");
                return false;
            }

            var raw = received.Text;
            if (string.IsNullOrWhiteSpace(raw))
                continue;

            _lastMessageAtUtc = _clock.UtcNow;
            _lastPongAtUtc = _clock.UtcNow;

            var (result, envelope) = EnvelopeValidator.ParseInbound(raw, _clock.UtcNow, agentId);
            if (result.IsValid && envelope?.MessageType == PortalMessageTypes.Connected)
                return true;

            if (TryReadMessageType(raw, out var messageType) &&
                string.Equals(messageType, PortalMessageTypes.PortalError, StringComparison.Ordinal))
            {
                _logger.LogWarning("Portal rejected agent.connect during handshake: {Payload}", raw);
                return false;
            }

            _logger.LogWarning("Unexpected Portal handshake response: {Code} - {Message}", result.ErrorCode, result.Message);
            return false;
        }

        return false;
    }

    private async Task HandleDisconnectAsync(IWebSocketTransport transport, string reason, CancellationToken ct)
    {
        _disconnectedAtUtc = _clock.UtcNow;
        _disconnectReason = reason;

        try { await transport.CloseAsync(reason, CancellationToken.None); }
        catch { /* melhor esforço — a conexão já pode estar morta */ }

        if (!ct.IsCancellationRequested)
        {
            await TransitionAsync(ConnectionState.Reconnecting, reason, null, CancellationToken.None);
            _logger.LogWarning("Conexão com o Portal encerrada ({Reason}). Reconectando.", reason);
        }
    }

    private readonly object _lock = new();
    private Channel<string>? _outbound;

    public async Task<bool> TrySendAsync(string messageType, object payload, string? correlationId = null, CancellationToken ct = default)
    {
        var identity = await _identity.GetIdentityAsync(ct);

        var envelope = ProtocolEnvelope.Create(
            messageType,
            payload,
            agentId: identity?.AgentId,
            installationId: identity?.InstallationId,
            agentInstanceId: identity?.InstanceId,
            correlationId: correlationId,
            sentAtUtc: _clock.UtcNow);

        if (!EnvelopeValidator.TrySerializeOutbound(envelope, out var json, out var error))
        {
            _logger.LogError("Mensagem {MessageType} não pôde ser enviada: {Error}", messageType, error);
            return false;
        }

        return await TrySendSerializedAsync(json, ct);
    }

    public Task<bool> TrySendSerializedAsync(string serializedEnvelope, CancellationToken ct = default)
    {
        Channel<string>? channel;
        lock (_lock) { channel = _outbound; }

        if (channel is null || !ConnectionStateMachine.IsOperational(_state))
            return Task.FromResult(false);

        // TryWrite é não bloqueante de propósito: "Try"Send não deve travar o chamador
        // (ex.: o laço do heartbeat) se a fila estiver cheia. Quando o Outbox existir
        // (Incremento 3), ele decide se tenta de novo depois — não aqui.
        return Task.FromResult(channel.Writer.TryWrite(serializedEnvelope));
    }

    private async Task SendLoopAsync(IWebSocketTransport transport, ChannelReader<string> reader, CancellationToken ct)
    {
        try
        {
            await foreach (var json in reader.ReadAllAsync(ct))
            {
                await transport.SendTextAsync(json, ct);
            }
        }
        catch (OperationCanceledException) { /* encerramento normal */ }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Laço de envio ao Portal encerrado por erro.");
        }
    }

    private async Task ReceiveLoopAsync(IWebSocketTransport transport, string agentId, CancellationToken ct)
    {
        try
        {
            while (!ct.IsCancellationRequested)
            {
                var result = await transport.ReceiveAsync(ct);

                switch (result.Kind)
                {
                    case TransportMessageKind.Text:
                        _lastMessageAtUtc = _clock.UtcNow;
                        _lastPongAtUtc = _clock.UtcNow; // qualquer tráfego conta como sinal de vida
                        await HandleInboundTextAsync(result.Text!, agentId, ct);
                        break;

                    case TransportMessageKind.Closed:
                        _logger.LogInformation("Portal encerrou a conexão: {Reason}", result.CloseReason);
                        return;

                    case TransportMessageKind.Error:
                        _logger.LogWarning(result.Error, "Erro ao receber mensagem do Portal.");
                        return;
                }
            }
        }
        catch (OperationCanceledException) { /* encerramento normal */ }
    }

    private async Task HandleInboundTextAsync(string rawJson, string agentId, CancellationToken ct)
    {
        var (result, envelope) = EnvelopeValidator.ParseInbound(rawJson, _clock.UtcNow, agentId);

        if (!result.IsValid || envelope is null)
        {
            _logger.LogWarning("Mensagem do Portal rejeitada: {Code} — {Message}", result.ErrorCode, result.Message);
            // A persistência em protocol_errors e o envio de protocol.error de volta
            // ao Portal são responsabilidade da camada que recebe este evento
            // (Command Dispatcher, Incremento 3+); aqui só registramos e descartamos.
            return;
        }

        var message = new InboundPortalMessage(
            envelope.MessageId,
            envelope.MessageType,
            envelope.CorrelationId,
            envelope.ExecutionId,
            envelope.ExecutionAttemptId,
            envelope.Sequence,
            envelope.Payload,
            _clock.UtcNow);

        var handler = MessageReceived;
        if (handler is not null)
        {
            foreach (Func<InboundPortalMessage, Task> subscriber in handler.GetInvocationList())
                await subscriber(message);
        }
    }

    /// <summary>
    /// Detecta conexão parada: nenhum tráfego (mensagem, ping/pong) por tempo excessivo.
    /// O próprio ClientWebSocket cuida do ping/pong de protocolo via KeepAliveInterval;
    /// este watchdog cobre o caso em que o socket TCP fica "meio aberto" sem que o SO
    /// perceba — situação clássica de rede que caiu sem enviar FIN/RST.
    /// </summary>
    private async Task WatchdogLoopAsync(CancellationToken ct)
    {
        var staleThreshold = TimeSpan.FromSeconds(Math.Max(_options.ConnectionTimeoutSeconds, _options.HeartbeatIntervalSeconds * 3));
        var checkInterval = TimeSpan.FromSeconds(Math.Max(1, _options.HeartbeatIntervalSeconds / 2));

        try
        {
            while (!ct.IsCancellationRequested)
            {
                await Task.Delay(checkInterval, ct);

                var lastSeen = _lastMessageAtUtc ?? _connectedAtUtc;
                if (lastSeen is null) continue;

                var silence = _clock.UtcNow - lastSeen.Value;
                if (silence > staleThreshold)
                {
                    _logger.LogWarning("Nenhum tráfego do Portal há {Silence:F0}s (limite {Threshold:F0}s); marcando conexão como parada.",
                        silence.TotalSeconds, staleThreshold.TotalSeconds);
                    return;
                }
            }
        }
        catch (OperationCanceledException) { /* encerramento normal */ }
    }

    public async Task DisableAsync(string reason, CancellationToken ct = default)
    {
        _disabledByRequest = true;
        _disconnectReason = reason;
        _wakeSignal?.Cancel();
        await Task.CompletedTask;
    }

    public async Task EnableAsync(CancellationToken ct = default)
    {
        _disabledByRequest = false;
        _wakeSignal?.Cancel();
        await Task.CompletedTask;
    }

    private async Task WaitForWakeSignalAsync(CancellationToken ct)
    {
        _wakeSignal = CancellationTokenSource.CreateLinkedTokenSource(ct);
        try { await Task.Delay(Timeout.InfiniteTimeSpan, _wakeSignal.Token); }
        catch (OperationCanceledException) { /* acordado por EnableAsync ou por ct externo */ }
    }

    public ConnectionStatus GetStatus() => new()
    {
        ConnectionId = _connectionId,
        State = _state,
        Endpoint = _options.WebSocketUrl,
        ConnectedAtUtc = _connectedAtUtc,
        DisconnectedAtUtc = _disconnectedAtUtc,
        LastMessageAtUtc = _lastMessageAtUtc,
        LastPongAtUtc = _lastPongAtUtc,
        DisconnectReason = _disconnectReason,
        ReconnectAttempt = _reconnectAttempt
    };

    private async Task TransitionAsync(ConnectionState to, string? reason, string? detail, CancellationToken ct)
    {
        await _stateLock.WaitAsync(CancellationToken.None);
        ConnectionState from;
        try
        {
            from = _state;
            if (from == to) return;

            if (!ConnectionStateMachine.CanTransition(from, to))
            {
                _logger.LogDebug("Transição de conexão ignorada: {From} -> {To} não é permitida.", from, to);
                return;
            }

            _state = to;
        }
        finally
        {
            _stateLock.Release();
        }

        await _stateRepo.RecordEventAsync(new ConnectionEvent
        {
            ConnectionId = _connectionId,
            FromState = from,
            ToState = to,
            Reason = reason,
            Detail = detail,
            OccurredAtUtc = _clock.UtcNow
        }, CancellationToken.None);

        await _stateRepo.SaveStatusAsync(GetStatus(), CancellationToken.None);

        var handler = StateChanged;
        if (handler is not null)
            await handler(from, to);
    }

    private Uri BuildConnectUri(string agentId, string installationId)
    {
        var baseUrl = _options.WebSocketUrl.TrimEnd('/');
        var separator = baseUrl.Contains('?') ? '&' : '?';
        return new Uri($"{baseUrl}{separator}agent_id={Uri.EscapeDataString(agentId)}&installation_id={Uri.EscapeDataString(installationId)}");
    }

    private static bool TryReadMessageType(string rawJson, out string? messageType)
    {
        messageType = null;
        try
        {
            using var document = JsonDocument.Parse(rawJson);
            if (!document.RootElement.TryGetProperty("message_type", out var value) ||
                value.ValueKind != JsonValueKind.String)
                return false;

            messageType = value.GetString();
            return !string.IsNullOrWhiteSpace(messageType);
        }
        catch (JsonException)
        {
            return false;
        }
    }

    private static async Task SafeAwaitAsync(Task task)
    {
        try { await task; }
        catch (OperationCanceledException) { /* esperado no encerramento */ }
        catch (Exception) { /* já logado na origem */ }
    }

    public async ValueTask DisposeAsync()
    {
        _wakeSignal?.Cancel();
        _wakeSignal?.Dispose();
        _runGate.Dispose();
        _stateLock.Dispose();
        await Task.CompletedTask;
    }
}
