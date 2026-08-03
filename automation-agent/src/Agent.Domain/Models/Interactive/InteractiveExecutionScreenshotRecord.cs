namespace Biason.AutomationAgent.Domain.Models.Interactive;

public sealed class InteractiveExecutionScreenshotRecord
{
    public string ArtifactId { get; init; } = default!;
    public string ExecutionId { get; init; } = default!;
    public string AttemptId { get; init; } = default!;
    public int SessionId { get; init; }
    public string Reason { get; init; } = default!;
    public string LocalPath { get; init; } = default!;
    public DateTime CapturedAtUtc { get; init; }
    public int? Width { get; init; }
    public int? Height { get; init; }
    public string? Sha256 { get; init; }
    public long SizeBytes { get; init; }
}
