using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Models.Messaging;
using Biason.AutomationAgent.Protocol.Messages;
using Biason.AutomationAgent.Protocol.Serialization;
using System.Text.Json;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

namespace Biason.AutomationAgent.Application.Messaging;

public sealed class PortalInboxService : IHostedService
{
    private readonly IPortalConnectionManager _connection;
    private readonly IInboxRepository _inbox;
    private readonly OutboxMessagePublisher _outboxPublisher;
    private readonly IMessageAcknowledgementRepository _acknowledgements;
    private readonly IClock _clock;
    private readonly ILogger<PortalInboxService> _logger;

    public PortalInboxService(
        IPortalConnectionManager connection,
        IInboxRepository inbox,
        OutboxMessagePublisher outboxPublisher,
        IMessageAcknowledgementRepository acknowledgements,
        IClock clock,
        ILogger<PortalInboxService> logger)
    {
        _connection = connection;
        _inbox = inbox;
        _outboxPublisher = outboxPublisher;
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
        if (!PortalMessageTypes.IsCommand(message.MessageType))
            return;

        var payloadJson = ProtocolJson.Serialize(message.Payload);
        var stored = await _inbox.StoreReceivedAsync(new InboxCommandDraft
        {
            MessageId = message.MessageId,
            CommandType = message.MessageType,
            PayloadJson = payloadJson,
            CorrelationId = message.CorrelationId,
            ExecutionId = message.ExecutionId,
            ExecutionAttemptId = message.ExecutionAttemptId,
            ReceivedAtUtc = message.ReceivedAtUtc
        });

        if (stored.IsDuplicate && !stored.PayloadMatches)
        {
            _logger.LogWarning(
                "Duplicate command {MessageId} has a different payload; keeping the first persisted command.",
                message.MessageId);

            await _outboxPublisher.EnqueueAsync(
                PortalMessageTypes.ProtocolError,
                new
                {
                    message_id = message.MessageId,
                    message_type = message.MessageType,
                    error_code = "DUPLICATE_MESSAGE_ID",
                    error_message = "Duplicate command message_id with different payload"
                },
                correlationId: message.MessageId,
                causationId: message.MessageId);
            return;
        }

        if (stored.IsDuplicate &&
            stored.Command.Status is InboxCommandStatus.Processed or InboxCommandStatus.DeadLetter)
        {
            await EnqueueCommandAckAsync(
                stored.Command,
                stored.Command.Status,
                duplicate: true,
                detail: "duplicate command already handled");
        }
    }

    public async Task EnqueueCommandAckAsync(InboxCommand command, string status, bool duplicate, string? detail)
    {
        await _outboxPublisher.EnqueueAsync(
            PortalMessageTypes.CommandAck,
            new CommandAcknowledgementPayload
            {
                CommandId = TryReadString(command.PayloadJson, "command_id"),
                CommandSequence = TryReadLong(command.PayloadJson, "command_sequence"),
                MessageId = command.MessageId,
                CommandType = command.CommandType,
                Status = status,
                Duplicate = duplicate,
                Detail = detail
            },
            correlationId: command.MessageId,
            causationId: command.MessageId);

        await _acknowledgements.SaveAsync(new MessageAcknowledgement
        {
            MessageId = command.MessageId,
            Direction = "outbound",
            Status = status,
            AcknowledgedAtUtc = _clock.UtcNow,
            Detail = detail
        });
    }

    private static string? TryReadString(string json, string propertyName)
    {
        try
        {
            using var document = JsonDocument.Parse(json);
            return document.RootElement.TryGetProperty(propertyName, out var value) &&
                   value.ValueKind == JsonValueKind.String
                ? value.GetString()
                : null;
        }
        catch (JsonException)
        {
            return null;
        }
    }

    private static long? TryReadLong(string json, string propertyName)
    {
        try
        {
            using var document = JsonDocument.Parse(json);
            if (!document.RootElement.TryGetProperty(propertyName, out var value))
                return null;

            return value.ValueKind switch
            {
                JsonValueKind.Number when value.TryGetInt64(out var number) => number,
                JsonValueKind.String when long.TryParse(value.GetString(), out var number) => number,
                _ => null
            };
        }
        catch (JsonException)
        {
            return null;
        }
    }
}
