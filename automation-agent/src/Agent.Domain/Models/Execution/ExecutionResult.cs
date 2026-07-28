namespace Biason.AutomationAgent.Domain.Models.Execution;

public sealed class ExecutionResult
{
    public string ExecutionId { get; init; } = default!;
    public string AttemptId { get; init; } = default!;
    public bool Success { get; init; }
    public int? ExitCode { get; init; }
    public string? OutputJson { get; init; }
    public string? ErrorOutput { get; init; }
    public long? DurationMs { get; init; }
    public long? PeakMemoryMb { get; init; }
    public double? CpuTimeSeconds { get; init; }
    public IReadOnlyList<ExecutionArtifactRef> Artifacts { get; init; } = Array.Empty<ExecutionArtifactRef>();
    public DateTime CompletedAtUtc { get; init; }
}

public sealed class ExecutionArtifactRef
{
    public string ArtifactId { get; init; } = default!;
    public string Name { get; init; } = default!;
    public string ContentType { get; init; } = default!;
    public long SizeBytes { get; init; }
    public string Sha256 { get; init; } = default!;
    public string LocalPath { get; init; } = default!;
}
