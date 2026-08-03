using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Models.Messaging;
using Biason.AutomationAgent.Domain.StateMachines;
using Biason.AutomationAgent.Protocol.Validation;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace Biason.AutomationAgent.Application.Messaging;

public sealed class OutboxBatchSender : BackgroundService
{
    private readonly IOutboxRepository _outbox;
    private readonly IPortalConnectionManager _connection;
    private readonly IAgentIdentityService _identity;
    private readonly IClock _clock;
    private readonly MessagingOptions _options;
    private readonly ILogger<OutboxBatchSender> _logger;

    public OutboxBatchSender(
        IOutboxRepository outbox,
        IPortalConnectionManager connection,
        IAgentIdentityService identity,
        IClock clock,
        IOptions<MessagingOptions> options,
        ILogger<OutboxBatchSender> logger)
    {
        _outbox = outbox;
        _connection = connection;
        _identity = identity;
        _clock = clock;
        _options = options.Value;
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        using var timer = new PeriodicTimer(TimeSpan.FromSeconds(_options.PollIntervalSeconds));

        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                await DispatchOnceAsync(stoppingToken);
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
            {
                break;
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Outbox batch sender cycle failed.");
            }

            try { await timer.WaitForNextTickAsync(stoppingToken); }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested) { break; }
        }
    }

    public async Task<int> DispatchOnceAsync(CancellationToken ct = default)
    {
        var now = _clock.UtcNow;
        await _outbox.RecoverTimedOutAsync(
            now,
            TimeSpan.FromSeconds(_options.AcknowledgementTimeoutSeconds),
            _options.MaxAttempts,
            ct);

        if (!ConnectionStateMachine.IsOperational(_connection.CurrentState))
            return 0;

        var identity = await _identity.GetIdentityAsync(ct);
        var batch = await _outbox.GetReadyBatchAsync(_options.OutboxBatchSize, now, ct);
        var sentCount = 0;

        foreach (var message in batch)
        {
            var envelope = OutboxMessagePublisher.BuildEnvelope(
                message.MessageId,
                message.MessageType,
                OutboxMessagePublisher.ReadPayloadElement(message.PayloadJson),
                message.AgentId ?? identity?.AgentId,
                identity?.InstallationId,
                identity?.InstanceId,
                message.ExecutionId,
                message.ExecutionAttemptId,
                message.Sequence,
                correlationId: null,
                causationId: null,
                sentAtUtc: _clock.UtcNow);

            if (!EnvelopeValidator.TrySerializeOutbound(envelope, out var json, out var error))
            {
                await _outbox.MarkDeadLetterAsync(message.Id, _clock.UtcNow, error ?? "Invalid outbound envelope", ct);
                continue;
            }

            var queued = await _connection.TrySendSerializedAsync(json, ct);
            if (!queued)
                break;

            await _outbox.MarkSentAsync(message.Id, _clock.UtcNow, ct);
            sentCount++;
        }

        return sentCount;
    }
}
