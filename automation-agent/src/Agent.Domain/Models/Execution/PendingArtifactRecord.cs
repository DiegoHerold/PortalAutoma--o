using Biason.AutomationAgent.Domain.Enums;

namespace Biason.AutomationAgent.Domain.Models.Execution;

public sealed class PendingArtifactRecord
{
    public string ArtifactId { get; init; } = default!;
    public string ExecutionId { get; init; } = default!;
    public string ExecutionAttemptId { get; init; } = default!;
    public string Name { get; init; } = default!;
    public string ContentType { get; init; } = "application/octet-stream";
    public long SizeBytes { get; init; }
    public string Sha256 { get; init; } = default!;
    public string LocalPath { get; init; } = default!;
    public ArtifactStatus Status { get; set; } = ArtifactStatus.Pending;
    public string? Kind { get; init; }
    public DateTime CreatedAtUtc { get; init; }
    public DateTime? AvailableAtUtc { get; set; }
    public DateTime? UploadedAtUtc { get; set; }
    public DateTime? ConfirmedAtUtc { get; set; }
    public string? RemoteObjectId { get; set; }
    public string? AnnouncementMessageId { get; set; }
    public string? UploadedMessageId { get; set; }
    public string? FailedMessageId { get; set; }
    public string? UploadSessionId { get; set; }
    public string? UploadUrl { get; set; }
    public string UploadMethod { get; set; } = "PUT";
    public string? UploadHeadersJson { get; set; }
    public DateTime? UploadExpiresAtUtc { get; set; }
    public int AttemptCount { get; set; }
    public string? LastError { get; set; }
}

public sealed record PendingArtifactDiagnostics(
    int Pending,
    int Announced,
    int UploadUrlReceived,
    int Uploading,
    int Uploaded,
    int Confirmed,
    int RetryWait,
    int Failed);
