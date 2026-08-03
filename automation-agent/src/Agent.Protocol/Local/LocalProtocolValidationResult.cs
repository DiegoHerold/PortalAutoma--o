namespace Biason.AutomationAgent.Protocol.Local;

public sealed class LocalProtocolValidationResult
{
    private LocalProtocolValidationResult(bool isValid, string? errorCode, string? message)
    {
        IsValid = isValid;
        ErrorCode = errorCode;
        Message = message;
    }

    public bool IsValid { get; }
    public string? ErrorCode { get; }
    public string? Message { get; }

    public static LocalProtocolValidationResult Valid { get; } = new(true, null, null);

    public static LocalProtocolValidationResult Invalid(string errorCode, string message) =>
        new(false, errorCode, message);
}
