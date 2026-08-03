namespace Biason.AutomationAgent.Protocol.Validation;

/// <summary>
/// Códigos de erro de protocolo. Enviados ao Portal em <c>protocol.error</c>
/// e persistidos em <c>protocol_errors</c>.
/// </summary>
public static class ProtocolErrorCodes
{
    public const string MalformedJson = "MALFORMED_JSON";
    public const string MissingProtocolVersion = "MISSING_PROTOCOL_VERSION";
    public const string UnsupportedProtocolVersion = "UNSUPPORTED_PROTOCOL_VERSION";
    public const string MissingMessageId = "MISSING_MESSAGE_ID";
    public const string MissingMessageType = "MISSING_MESSAGE_TYPE";
    public const string UnknownMessageType = "UNKNOWN_MESSAGE_TYPE";
    public const string UnexpectedDirection = "UNEXPECTED_DIRECTION";
    public const string MissingSentAt = "MISSING_SENT_AT";
    public const string ClockSkewTooLarge = "CLOCK_SKEW_TOO_LARGE";
    public const string PayloadTooLarge = "PAYLOAD_TOO_LARGE";
    public const string InvalidPayload = "INVALID_PAYLOAD";
    public const string AgentMismatch = "AGENT_MISMATCH";
}

public sealed record EnvelopeValidationResult(bool IsValid, string? ErrorCode = null, string? Message = null)
{
    public static readonly EnvelopeValidationResult Valid = new(true);

    public static EnvelopeValidationResult Invalid(string errorCode, string message) =>
        new(false, errorCode, message);
}
