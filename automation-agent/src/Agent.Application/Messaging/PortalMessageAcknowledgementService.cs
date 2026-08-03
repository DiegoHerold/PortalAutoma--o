using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Models.Messaging;
using Biason.AutomationAgent.Protocol.Messages;
using Biason.AutomationAgent.Protocol.Serialization;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

namespace Biason.AutomationAgent.Application.Messaging;

public sealed class PortalMessageAcknowledgementService : IHostedService
{
    private readonly IPortalConnectionManager _connection;
    private readonly IOutboxRepository _outbox;
    private readonly IMessageAcknowledgementRepository _acknowledgements;
    private readonly IClock _clock;
    private readonly ILogger<PortalMessageAcknowledgementService> _logger;

    public PortalMessageAcknowledgementService(
        IPortalConnectionManager connection,
        IOutboxRepository outbox,
        IMessageAcknowledgementRepository acknowledgements,
        IClock clock,
        ILogger<PortalMessageAcknowledgementService> logger)
    {
        _connection = connection;
        _outbox = outbox;
        _acknowledgements = acknowledgements;
        _clock = clock;
        _logger = logger;
    }

    public Task StartAsync(CancellationToken cancellationToken)
    {
        _connection.MessageReceived += HandleMessageAsync;
        return Task.CompletedTask;
    }

    public Task StopAsync(CancellationToken cancellationToken)
    {
        _connection.MessageReceived -= HandleMessageAsync;
        return Task.CompletedTask;
    }

    public async Task HandleMessageAsync(InboundPortalMessage message)
    {
        if (message.MessageType != PortalMessageTypes.MessageAck)
            return;

        var payload = ProtocolJson.ReadPayload<MessageAcknowledgementPayload>(message.Payload);
        if (payload is null)
        {
            if (!string.IsNullOrWhiteSpace(message.CorrelationId))
            {
                await AcknowledgeMessageAsync(
                    message.CorrelationId,
                    status: "acknowledged",
                    detail: "acknowledged by correlation_id",
                    nowUtc: _clock.UtcNow);
                return;
            }

            _logger.LogWarning("message.ack {MessageId} ignored: invalid payload.", message.MessageId);
            return;
        }

        var now = _clock.UtcNow;
        var detail = payload.Detail ?? payload.Status;

        if (!string.IsNullOrWhiteSpace(payload.MessageId))
            await AcknowledgeMessageAsync(payload.MessageId, payload.Status, detail, now);

        if (payload.MessageIds is not null)
        {
            foreach (var messageId in payload.MessageIds.Where(id => !string.IsNullOrWhiteSpace(id)))
                await AcknowledgeMessageAsync(messageId, payload.Status, detail, now);
        }

        if (!string.IsNullOrWhiteSpace(payload.ExecutionAttemptId) &&
            payload.LastContiguousSequence is not null)
        {
            var count = await _outbox.MarkAcknowledgedThroughSequenceAsync(
                payload.ExecutionAttemptId,
                payload.LastContiguousSequence.Value,
                now,
                detail);

            await _acknowledgements.SaveAsync(new MessageAcknowledgement
            {
                MessageId = message.MessageId,
                Direction = "inbound",
                Status = payload.Status,
                AcknowledgedAtUtc = now,
                Detail = $"acknowledged {count} message(s) through sequence {payload.LastContiguousSequence}"
            });
        }
    }

    private async Task AcknowledgeMessageAsync(string messageId, string status, string? detail, DateTime nowUtc)
    {
        await _outbox.MarkAcknowledgedAsync(messageId, nowUtc, detail);
        await _acknowledgements.SaveAsync(new MessageAcknowledgement
        {
            MessageId = messageId,
            Direction = "inbound",
            Status = status,
            AcknowledgedAtUtc = nowUtc,
            Detail = detail
        });
    }
}
