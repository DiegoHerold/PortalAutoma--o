namespace Biason.AutomationAgent.Domain.Models.Sessions;

public sealed class SessionEventRecord
{
    public long Id { get; init; }
    public int? SessionId { get; init; }
    public string? SessionRunnerInstanceId { get; init; }
    public string EventType { get; init; } = default!;
    public string? DetailJson { get; init; }
    public DateTime OccurredAtUtc { get; init; }
}
