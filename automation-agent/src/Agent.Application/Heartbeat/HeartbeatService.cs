using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.StateMachines;
using Biason.AutomationAgent.Protocol.Messages;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace Biason.AutomationAgent.Application.Heartbeat;

/// <summary>
/// Envia <c>agent.heartbeat</c> periodicamente enquanto a conexão está operacional
/// (seção 16) e rastreia o último <c>agent.heartbeat_ack</c> recebido, para uso por
/// health checks (uma conexão "Connected" sem acks recentes é sinal de Portal
/// respondendo devagar, mesmo que o socket em si esteja de pé).
///
/// Não decide quando conectar/desconectar — só usa <see cref="IPortalConnectionManager.TrySendAsync"/>,
/// que já lida com "não há conexão agora" retornando false (heartbeat perdido é
/// aceitável; o próximo tick tenta de novo).
/// </summary>
public sealed class HeartbeatService : BackgroundService
{
    private readonly IPortalConnectionManager _connection;
    private readonly HeartbeatSnapshotBuilder _snapshotBuilder;
    private readonly IClock _clock;
    private readonly PortalOptions _options;
    private readonly IOutboxRepository? _outbox;
    private readonly ILogger<HeartbeatService> _logger;

    private DateTime? _lastSentAtUtc;
    private DateTime? _lastAckAtUtc;
    private string? _lastCorrelationId;

    public HeartbeatService(
        IPortalConnectionManager connection,
        HeartbeatSnapshotBuilder snapshotBuilder,
        IClock clock,
        IOptions<PortalOptions> options,
        ILogger<HeartbeatService> logger,
        IOutboxRepository? outbox = null)
    {
        _connection = connection;
        _snapshotBuilder = snapshotBuilder;
        _clock = clock;
        _options = options.Value;
        _outbox = outbox;
        _logger = logger;

        _connection.MessageReceived += OnMessageReceivedAsync;
    }

    /// <summary>Último heartbeat enviado, para diagnóstico/health check.</summary>
    public DateTime? LastSentAtUtc => _lastSentAtUtc;

    /// <summary>Último <c>agent.heartbeat_ack</c> recebido. Null enquanto nenhum ack chegou.</summary>
    public DateTime? LastAckAtUtc => _lastAckAtUtc;

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        if (!_options.Enabled)
        {
            _logger.LogInformation("Integração com o Portal desabilitada; HeartbeatService não inicia.");
            return;
        }

        var interval = TimeSpan.FromSeconds(_options.HeartbeatIntervalSeconds);
        using var timer = new PeriodicTimer(interval);

        // Primeiro heartbeat imediato — não espera um ciclo inteiro após conectar.
        await SendHeartbeatAsync(stoppingToken);

        try
        {
            while (await timer.WaitForNextTickAsync(stoppingToken))
            {
                await SendHeartbeatAsync(stoppingToken);
            }
        }
        catch (OperationCanceledException)
        {
            // encerramento normal do host
        }
    }

    private async Task SendHeartbeatAsync(CancellationToken ct)
    {
        if (!ConnectionStateMachine.IsOperational(_connection.CurrentState))
            return;

        try
        {
            var status = _connection.GetStatus();
            var outboxPending = _outbox is null ? 0 : await _outbox.CountPendingAsync(ct);
            var payload = await _snapshotBuilder.BuildAsync(
                _connection.CurrentState,
                outboxPending: outboxPending,
                pendingArtifacts: 0, // Upload de artefatos chega no Incremento 6.
                ct);

            var correlationId = $"hb_{Guid.NewGuid():N}";
            var sent = await _connection.TrySendAsync(PortalMessageTypes.Heartbeat, payload, correlationId, ct);

            if (sent)
            {
                _lastSentAtUtc = _clock.UtcNow;
                _lastCorrelationId = correlationId;
                _logger.LogDebug("Heartbeat enviado (conexão {ConnectionId}, estado {State}).", status.ConnectionId, status.State);
            }
            else
            {
                _logger.LogDebug("Heartbeat não enviado: conexão não operacional no momento do envio.");
            }
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Falha ao montar/enviar heartbeat.");
        }
    }

    private Task OnMessageReceivedAsync(InboundPortalMessage message)
    {
        if (message.MessageType == PortalMessageTypes.HeartbeatAck)
        {
            _lastAckAtUtc = _clock.UtcNow;

            // Correlacionar não é obrigatório (qualquer ack é sinal de vida do Portal),
            // mas ajuda a diagnosticar acks atrasados/fora de ordem nos logs.
            var matchesLastSent = string.Equals(message.CorrelationId, _lastCorrelationId, StringComparison.Ordinal);
            _logger.LogDebug(
                "Heartbeat ack recebido (correlation_id={CorrelationId}, corresponde ao último enviado={Matches}).",
                message.CorrelationId, matchesLastSent);
        }

        return Task.CompletedTask;
    }

    public override void Dispose()
    {
        _connection.MessageReceived -= OnMessageReceivedAsync;
        base.Dispose();
    }
}
