namespace Biason.AutomationAgent.Domain.Models.Sessions;

public sealed class InteractiveExecutionToken
{
    public string Token { get; init; } = default!;
    public string Fingerprint { get; init; } = default!;
    public string ExecutionId { get; init; } = default!;
    public string ExecutionAttemptId { get; init; } = default!;
    public int SessionId { get; init; }
    public string SessionRunnerInstanceId { get; init; } = default!;
    public DateTime ExpiresAtUtc { get; init; }
}
