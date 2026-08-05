namespace Biason.AutomationAgent.Domain.Models.Execution;

public sealed class SyncRunRecord
{
    public string SyncId { get; init; } = default!;
    public string? ConnectionId { get; init; }
    public DateTime StartedAtUtc { get; init; }
    public DateTime? CompletedAtUtc { get; set; }
    public int RunningExecutionsReported { get; set; }
    public int LeasesReported { get; set; }
    public int OutboxPendingReported { get; set; }
    public int ReconciledCount { get; set; }
    public string Status { get; set; } = "running";
    public string? ErrorMessage { get; set; }
}
