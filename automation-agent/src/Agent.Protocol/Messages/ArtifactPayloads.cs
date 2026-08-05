using System.Text.Json.Serialization;

namespace Biason.AutomationAgent.Protocol.Messages;

public sealed class ExecutionArtifactCreatedPayload
{
    [JsonPropertyName("artifact_id")]
    public string ArtifactId { get; init; } = default!;

    [JsonPropertyName("execution_id")]
    public string ExecutionId { get; init; } = default!;

    [JsonPropertyName("execution_attempt_id")]
    public string ExecutionAttemptId { get; init; } = default!;

    [JsonPropertyName("name")]
    public string Name { get; init; } = default!;

    [JsonPropertyName("content_type")]
    public string ContentType { get; init; } = "application/octet-stream";

    [JsonPropertyName("size_bytes")]
    public long SizeBytes { get; init; }

    [JsonPropertyName("sha256")]
    public string Sha256 { get; init; } = default!;

    [JsonPropertyName("status")]
    public string Status { get; init; } = "PENDING";
}

public sealed class ArtifactConfirmedPayload
{
    [JsonPropertyName("artifact_id")]
    public string ArtifactId { get; init; } = default!;

    [JsonPropertyName("execution_id")]
    public string? ExecutionId { get; init; }

    [JsonPropertyName("execution_attempt_id")]
    public string? ExecutionAttemptId { get; init; }

    [JsonPropertyName("remote_object_id")]
    public string? RemoteObjectId { get; init; }
}

public sealed class ArtifactUploadedPayload
{
    [JsonPropertyName("artifact_id")]
    public string ArtifactId { get; init; } = default!;

    [JsonPropertyName("execution_id")]
    public string ExecutionId { get; init; } = default!;

    [JsonPropertyName("execution_attempt_id")]
    public string ExecutionAttemptId { get; init; } = default!;

    [JsonPropertyName("upload_session_id")]
    public string UploadSessionId { get; init; } = default!;

    [JsonPropertyName("size_bytes")]
    public long SizeBytes { get; init; }

    [JsonPropertyName("sha256")]
    public string Sha256 { get; init; } = default!;
}

public sealed class ArtifactFailedPayload
{
    [JsonPropertyName("artifact_id")]
    public string ArtifactId { get; init; } = default!;

    [JsonPropertyName("execution_id")]
    public string ExecutionId { get; init; } = default!;

    [JsonPropertyName("execution_attempt_id")]
    public string ExecutionAttemptId { get; init; } = default!;

    [JsonPropertyName("upload_session_id")]
    public string? UploadSessionId { get; init; }

    [JsonPropertyName("reason")]
    public string Reason { get; init; } = default!;
}
