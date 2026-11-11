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
    private readonly ExecutionAttemptSequenceTracker _sequences;

    public OutboxMessagePublisher(
        IOutboxRepository outbox,
        IAgentIdentityService identity,
        IClock clock,
        ExecutionAttemptSequenceTracker? sequences = null)
    {
        _outbox = outbox;
        _identity = identity;
        _clock = clock;
        _sequences = sequences ?? new ExecutionAttemptSequenceTracker();
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
        var id = messageId ?? ProtocolEnvelope.NewMessageId();
        var effectiveSequence = sequence ?? NextAttemptSequence(messageType, executionAttemptId);
        var normalized = NormalizeOutboundMessage(
            id,
            messageType,
            payload,
            identity?.AgentId,
            identity?.InstanceId,
            executionAttemptId,
            effectiveSequence,
            now);
        var payloadJson = normalized.PayloadJson;

        var envelope = BuildEnvelope(
            id,
            normalized.MessageType,
            ReadPayloadElement(payloadJson),
            identity?.AgentId,
            identity?.InstallationId,
            identity?.InstanceId,
            executionId,
            executionAttemptId,
            effectiveSequence,
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
            MessageType = normalized.MessageType,
            PayloadJson = payloadJson,
            AgentId = identity?.AgentId,
            ExecutionId = executionId,
            ExecutionAttemptId = executionAttemptId,
            Sequence = effectiveSequence,
            CreatedAtUtc = now,
            AvailableAtUtc = now,
            Status = status,
            PayloadSizeBytes = Encoding.UTF8.GetByteCount(payloadJson),
            LastError = lastError
        }, ct);
    }

    private long? NextAttemptSequence(string messageType, string? executionAttemptId)
    {
        if (string.IsNullOrWhiteSpace(executionAttemptId) || !RequiresAttemptSequence(messageType))
            return null;

        return _sequences.Next(executionAttemptId);
    }

    private static bool RequiresAttemptSequence(string messageType) => messageType switch
    {
        PortalMessageTypes.ExecutionLog => true,
        PortalMessageTypes.ExecutionProgress => true,
        PortalMessageTypes.ExecutionMetric => true,
        PortalMessageTypes.AutomationEvent => true,
        PortalMessageTypes.ExecutionPreparing => true,
        PortalMessageTypes.ExecutionCancelling => true,
        PortalMessageTypes.LeaseLost => true,
        PortalMessageTypes.ExecutionCommitRejected => true,
        PortalMessageTypes.ExecutionCompleted => true,
        PortalMessageTypes.ExecutionFailed => true,
        PortalMessageTypes.ExecutionCancelled => true,
        PortalMessageTypes.ExecutionTimedOut => true,
        _ => false
    };

    private static NormalizedOutboundMessage NormalizeOutboundMessage(
        string messageId,
        string messageType,
        object? payload,
        string? agentId,
        string? agentInstanceId,
        string? executionAttemptId,
        long? sequence,
        DateTime nowUtc)
    {
        var payloadJson = ProtocolJson.Serialize(payload);
        return messageType switch
        {
            PortalMessageTypes.ExecutionLog => ToEventBatch(
                messageId,
                executionAttemptId,
                "log",
                payloadJson,
                sequence,
                nowUtc,
                level: "INFO"),

            PortalMessageTypes.ExecutionProgress => ToEventBatch(
                messageId,
                executionAttemptId,
                "task.progress",
                payloadJson,
                sequence,
                nowUtc),

            PortalMessageTypes.ExecutionMetric => ToEventBatch(
                messageId,
                executionAttemptId,
                "metric",
                payloadJson,
                sequence,
                nowUtc),

            // O evento da automacao vai intacto: o Portal valida pelo contrato automation-events/v1.
            PortalMessageTypes.AutomationEvent => ToEventBatch(
                messageId,
                executionAttemptId,
                "automation.event",
                payloadJson,
                sequence,
                nowUtc),

            PortalMessageTypes.ExecutionPreparing => ToEventBatch(
                messageId,
                executionAttemptId,
                "diagnostic",
                MergePayload(payloadJson, new Dictionary<string, object?> { ["phase"] = "preparing" }),
                sequence,
                nowUtc),

            PortalMessageTypes.ExecutionCancelling => ToEventBatch(
                messageId,
                executionAttemptId,
                "warning",
                MergePayload(payloadJson, new Dictionary<string, object?> { ["phase"] = "cancelling" }),
                sequence,
                nowUtc,
                level: "WARNING"),

            PortalMessageTypes.LeaseLost => ToEventBatch(
                messageId,
                executionAttemptId,
                "error",
                MergePayload(payloadJson, new Dictionary<string, object?> { ["phase"] = "lease_lost" }),
                sequence,
                nowUtc,
                level: "ERROR"),

            PortalMessageTypes.ExecutionCommitRejected => ToTerminalPayload(
                PortalMessageTypes.ExecutionFailed,
                payloadJson,
                agentId,
                agentInstanceId,
                executionAttemptId,
                sequence,
                nowUtc,
                timestampField: "failed_at",
                defaultCode: "COMMIT_REJECTED"),

            PortalMessageTypes.ExecutionStarted => ToStartedPayload(
                payloadJson,
                agentId,
                agentInstanceId,
                executionAttemptId,
                nowUtc),

            PortalMessageTypes.ExecutionCompleted => ToTerminalPayload(
                PortalMessageTypes.ExecutionCompleted,
                payloadJson,
                agentId,
                agentInstanceId,
                executionAttemptId,
                sequence,
                nowUtc,
                timestampField: "completed_at",
                defaultCode: null),

            PortalMessageTypes.ExecutionFailed => ToTerminalPayload(
                PortalMessageTypes.ExecutionFailed,
                payloadJson,
                agentId,
                agentInstanceId,
                executionAttemptId,
                sequence,
                nowUtc,
                timestampField: "failed_at",
                defaultCode: "EXECUTION_FAILED"),

            PortalMessageTypes.ExecutionCancelled => ToTerminalPayload(
                PortalMessageTypes.ExecutionCancelled,
                payloadJson,
                agentId,
                agentInstanceId,
                executionAttemptId,
                sequence,
                nowUtc,
                timestampField: "cancelled_at",
                defaultCode: "EXECUTION_CANCELLED"),

            PortalMessageTypes.ExecutionTimedOut => ToTerminalPayload(
                PortalMessageTypes.ExecutionTimedOut,
                payloadJson,
                agentId,
                agentInstanceId,
                executionAttemptId,
                sequence,
                nowUtc,
                timestampField: "timed_out_at",
                defaultCode: "EXECUTION_TIMED_OUT"),

            _ => new NormalizedOutboundMessage(messageType, payloadJson)
        };
    }

    private static NormalizedOutboundMessage ToEventBatch(
        string messageId,
        string? executionAttemptId,
        string eventType,
        string payloadJson,
        long? sequence,
        DateTime nowUtc,
        string? level = null)
    {
        var attemptId = executionAttemptId ?? TryReadString(payloadJson, "execution_attempt_id") ?? "";
        var eventSequence = sequence ?? TryReadLong(payloadJson, "event_sequence") ?? NextSyntheticSequence();
        var eventPayload = ReadPayloadElement(payloadJson);
        var evt = new Dictionary<string, object?>
        {
            ["event_id"] = $"{messageId}:1",
            ["event_sequence"] = eventSequence,
            ["event_type"] = eventType,
            ["occurred_at"] = nowUtc,
            ["payload"] = eventPayload
        };
        if (!string.IsNullOrWhiteSpace(level))
            evt["level"] = level;

        var batch = new
        {
            execution_attempt_id = attemptId,
            events = new[] { evt }
        };
        return new NormalizedOutboundMessage(PortalMessageTypes.ExecutionEventBatch, ProtocolJson.Serialize(batch));
    }

    private static NormalizedOutboundMessage ToStartedPayload(
        string payloadJson,
        string? agentId,
        string? agentInstanceId,
        string? executionAttemptId,
        DateTime nowUtc)
    {
        var payload = ToPayloadDictionary(payloadJson);
        Ensure(payload, "execution_attempt_id", executionAttemptId ?? TryReadString(payloadJson, "execution_attempt_id"));
        Ensure(payload, "agent_id", agentId);
        Ensure(payload, "agent_instance_id", agentInstanceId);
        Ensure(payload, "started_at", nowUtc);
        return new NormalizedOutboundMessage(PortalMessageTypes.ExecutionStarted, ProtocolJson.Serialize(payload));
    }

    private static NormalizedOutboundMessage ToTerminalPayload(
        string wireMessageType,
        string payloadJson,
        string? agentId,
        string? agentInstanceId,
        string? executionAttemptId,
        long? sequence,
        DateTime nowUtc,
        string timestampField,
        string? defaultCode)
    {
        var payload = ToPayloadDictionary(payloadJson);
        Ensure(payload, "execution_attempt_id", executionAttemptId ?? TryReadString(payloadJson, "execution_attempt_id"));
        Ensure(payload, "agent_id", agentId);
        Ensure(payload, "agent_instance_id", agentInstanceId);
        Ensure(payload, "event_sequence", sequence ?? TryReadLong(payloadJson, "event_sequence") ?? NextSyntheticSequence());
        Ensure(payload, timestampField, nowUtc);
        if (!string.IsNullOrWhiteSpace(defaultCode))
            Ensure(payload, "code", defaultCode);
        return new NormalizedOutboundMessage(wireMessageType, ProtocolJson.Serialize(payload));
    }

    private static string MergePayload(string payloadJson, IReadOnlyDictionary<string, object?> additions)
    {
        var payload = ToPayloadDictionary(payloadJson);
        foreach (var item in additions)
            payload[item.Key] = item.Value;
        return ProtocolJson.Serialize(payload);
    }

    private static Dictionary<string, object?> ToPayloadDictionary(string payloadJson)
    {
        try
        {
            return JsonSerializer.Deserialize<Dictionary<string, object?>>(payloadJson, ProtocolJson.Options)
                   ?? new Dictionary<string, object?>(StringComparer.Ordinal);
        }
        catch (JsonException)
        {
            return new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["raw"] = payloadJson
            };
        }
    }

    private static void Ensure(Dictionary<string, object?> payload, string key, object? value)
    {
        if (!payload.ContainsKey(key) && value is not null)
            payload[key] = value;
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

    private static long NextSyntheticSequence() =>
        Interlocked.Increment(ref _syntheticEventSequence);

    private static long _syntheticEventSequence = DateTimeOffset.UtcNow.ToUnixTimeSeconds();

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

    private sealed record NormalizedOutboundMessage(string MessageType, string PayloadJson);
}
