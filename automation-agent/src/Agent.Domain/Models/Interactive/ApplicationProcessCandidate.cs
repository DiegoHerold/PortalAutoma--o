namespace Biason.AutomationAgent.Domain.Models.Interactive;

public sealed class ApplicationProcessCandidate
{
    public string ApplicationKey { get; init; } = default!;
    public int ProcessId { get; init; }
    public int? SessionId { get; init; }
    public string? ProcessPath { get; init; }
    public DateTime? StartedAtUtc { get; init; }
    public string? WindowTitle { get; init; }
    public string? ProcessOwner { get; init; }
}
