namespace Biason.AutomationAgent.Domain.Contracts;

public interface ISessionRunnerProcessValidator
{
    Task<SessionRunnerProcessValidationResult> ValidateAsync(
        int actualProcessId,
        int declaredProcessId,
        int declaredSessionId,
        CancellationToken ct = default);
}

public sealed class SessionRunnerProcessValidationResult
{
    public bool IsValid { get; init; }
    public string? ErrorCode { get; init; }
    public string? Message { get; init; }
    public string? ExecutablePath { get; init; }
    public int? ActualSessionId { get; init; }

    public static SessionRunnerProcessValidationResult Valid(string? executablePath, int actualSessionId) =>
        new() { IsValid = true, ExecutablePath = executablePath, ActualSessionId = actualSessionId };

    public static SessionRunnerProcessValidationResult Invalid(string errorCode, string message, string? executablePath = null, int? actualSessionId = null) =>
        new() { IsValid = false, ErrorCode = errorCode, Message = message, ExecutablePath = executablePath, ActualSessionId = actualSessionId };
}
