using System.Text;
using System.Text.Json;
using Biason.AutomationAgent.Protocol.Envelope;
using Biason.AutomationAgent.Protocol.Serialization;
using Biason.AutomationAgent.Protocol.Validation;

namespace Biason.AutomationAgent.Protocol.Local;

public static class LocalProtocolValidator
{
    public static (LocalProtocolValidationResult Result, LocalProtocolEnvelope? Envelope) Parse(
        string rawJson,
        DateTime nowUtc,
        int maxSizeBytes,
        string expectedVersion = ProtocolConstants.CurrentVersion)
    {
        if (string.IsNullOrWhiteSpace(rawJson))
            return (LocalProtocolValidationResult.Invalid(LocalProtocolErrors.MalformedJson, "Empty local message."), null);

        var size = Encoding.UTF8.GetByteCount(rawJson);
        if (size > maxSizeBytes)
        {
            return (LocalProtocolValidationResult.Invalid(
                LocalProtocolErrors.MessageTooLarge,
                $"Local message has {size} bytes and exceeds {maxSizeBytes} bytes."), null);
        }

        LocalProtocolEnvelope? envelope;
        try
        {
            envelope = ProtocolJson.Deserialize<LocalProtocolEnvelope>(rawJson);
        }
        catch (JsonException ex)
        {
            return (LocalProtocolValidationResult.Invalid(LocalProtocolErrors.MalformedJson, ex.Message), null);
        }

        if (envelope is null)
            return (LocalProtocolValidationResult.Invalid(LocalProtocolErrors.MalformedJson, "Null local envelope."), null);

        var validation = Validate(envelope, nowUtc, expectedVersion);
        return (validation, validation.IsValid ? envelope : null);
    }

    public static LocalProtocolValidationResult Validate(
        LocalProtocolEnvelope envelope,
        DateTime nowUtc,
        string expectedVersion = ProtocolConstants.CurrentVersion)
    {
        if (!EnvelopeValidator.IsVersionCompatible(envelope.ProtocolVersion, out var error))
            return LocalProtocolValidationResult.Invalid(LocalProtocolErrors.UnsupportedProtocolVersion, error!);

        if (!string.Equals(envelope.ProtocolVersion, expectedVersion, StringComparison.Ordinal))
            return LocalProtocolValidationResult.Invalid(LocalProtocolErrors.UnsupportedProtocolVersion, $"Expected local protocol {expectedVersion}.");

        if (string.IsNullOrWhiteSpace(envelope.MessageId))
            return LocalProtocolValidationResult.Invalid(LocalProtocolErrors.MissingMessageId, "message_id is required.");

        if (string.IsNullOrWhiteSpace(envelope.MessageType))
            return LocalProtocolValidationResult.Invalid(LocalProtocolErrors.MissingMessageType, "message_type is required.");

        if (!LocalMessageTypes.Known.Contains(envelope.MessageType))
            return LocalProtocolValidationResult.Invalid(LocalProtocolErrors.UnknownMessageType, $"Unknown local message type: {envelope.MessageType}");

        if (envelope.SentAt == default)
            return LocalProtocolValidationResult.Invalid(LocalProtocolErrors.MissingSentAt, "sent_at is required.");

        var skew = (envelope.SentAt - nowUtc).Duration();
        if (skew > ProtocolConstants.MaxClockSkew)
            return LocalProtocolValidationResult.Invalid(ProtocolErrorCodes.ClockSkewTooLarge, $"sent_at clock skew is {skew.TotalMinutes:F1} minutes.");

        return LocalProtocolValidationResult.Valid;
    }
}
