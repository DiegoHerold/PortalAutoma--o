using System.Text;
using System.Text.Json;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Models.Messaging;
using Biason.AutomationAgent.Protocol.Envelope;
using Biason.AutomationAgent.Protocol.Messages;
using Biason.AutomationAgent.Protocol.Serialization;
using Biason.AutomationAgent.Protocol.Validation;

namespace Biason.AutomationAgent.Application.Messaging;

public sealed class OutboxMessagePublisher
{
    private readonly IOutboxRepository _outbox;
    private readonly IAgentIdentityService _identity;
    private readonly IClock _clock;

    public OutboxMessagePublisher(IOutboxRepository outbox, IAgentIdentityService identity, IClock clock)
    {
        _outbox = outbox;
        _identity = identity;
        _clock = clock;
    }

    public async Task<OutboxMessage> EnqueueAsync(
        string messageType,
        object? payload,
        string? correlationId = null,
        string? causationId = null,
        string? executionId = null,
        string? executionAttemptId = null,
        long? sequence = null,
        string? messageId = null,
        CancellationToken ct = default)
    {
        if (!PortalMessageTypes.Outbound.Contains(messageType))
            throw new ArgumentException($"Message type '{messageType}' is not outbound for the Agent.", nameof(messageType));

        var identity = await _identity.GetIdentityAsync(ct);
        var now = _clock.UtcNow;
        var payloadJson = ProtocolJson.Serialize(payload);
        var id = messageId ?? ProtocolEnvelope.NewMessageId();

        var envelope = BuildEnvelope(
            id,
            messageType,
            ReadPayloadElement(payloadJson),
            identity?.AgentId,
            identity?.InstallationId,
            identity?.InstanceId,
            executionId,
            executionAttemptId,
            sequence,
            correlationId,
            causationId,
            now);

        var status = OutboxMessageStatus.Pending;
        string? lastError = null;
        if (!EnvelopeValidator.TrySerializeOutbound(envelope, out _, out var error))
        {
            status = OutboxMessageStatus.DeadLetter;
            lastError = error;
        }

        return await _outbox.EnqueueAsync(new OutboxMessageDraft
        {
            MessageId = id,
            MessageType = messageType,
            PayloadJson = payloadJson,
            AgentId = identity?.AgentId,
            ExecutionId = executionId,
            ExecutionAttemptId = executionAttemptId,
            Sequence = sequence,
            CreatedAtUtc = now,
            AvailableAtUtc = now,
            Status = status,
            PayloadSizeBytes = Encoding.UTF8.GetByteCount(payloadJson),
            LastError = lastError
        }, ct);
    }

    internal static ProtocolEnvelope BuildEnvelope(
        string messageId,
        string messageType,
        object? payload,
        string? agentId,
        string? installationId,
        string? agentInstanceId,
        string? executionId,
        string? executionAttemptId,
        long? sequence,
        string? correlationId,
        string? causationId,
        DateTime sentAtUtc)
    {
        return new ProtocolEnvelope
        {
            MessageId = messageId,
            MessageType = messageType,
            SentAt = sentAtUtc,
            AgentId = agentId,
            InstallationId = installationId,
            AgentInstanceId = agentInstanceId,
            ExecutionId = executionId,
            ExecutionAttemptId = executionAttemptId,
            Sequence = sequence,
            CorrelationId = correlationId,
            CausationId = causationId,
            Payload = payload
        };
    }

    internal static JsonElement ReadPayloadElement(string payloadJson)
    {
        using var document = JsonDocument.Parse(payloadJson);
        return document.RootElement.Clone();
    }
}
