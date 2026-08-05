using System.Globalization;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Execution;
using Biason.AutomationAgent.Infrastructure.Database;
using Microsoft.Data.Sqlite;

namespace Biason.AutomationAgent.Infrastructure.Persistence;

public sealed class PendingArtifactRepository : IPendingArtifactRepository
{
    private readonly SqliteDatabaseManager _db;

    public PendingArtifactRepository(SqliteDatabaseManager db) => _db = db;

    public async Task SaveAsync(PendingArtifactRecord artifact, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            INSERT INTO pending_artifacts (
                artifact_id, execution_id, execution_attempt_id, name, content_type, size_bytes,
                sha256, local_path, status, kind, created_at_utc, available_at_utc, uploaded_at_utc,
                confirmed_at_utc, remote_object_id, announcement_message_id, uploaded_message_id,
                failed_message_id, upload_session_id, upload_url, upload_method, upload_headers_json,
                upload_expires_at_utc, attempt_count, last_error
            ) VALUES (
                $id, $eid, $aid, $name, $contentType, $size, $sha, $path, $status, $kind,
                $created, $available, $uploaded, $confirmed, $remote, $announcementMessageId,
                $uploadedMessageId, $failedMessageId, $uploadSessionId, $uploadUrl, $uploadMethod,
                $uploadHeadersJson, $uploadExpiresAt, $attempts, $error
            )
            ON CONFLICT(artifact_id) DO NOTHING;
            """;
        BindAll(cmd, artifact);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task<PendingArtifactRecord?> GetAsync(string artifactId, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT * FROM pending_artifacts WHERE artifact_id = $id;";
        cmd.Parameters.AddWithValue("$id", artifactId);
        using var r = await cmd.ExecuteReaderAsync(ct);
        return await r.ReadAsync(ct) ? Map(r) : null;
    }

    public async Task<IReadOnlyList<PendingArtifactRecord>> GetUploadCandidatesAsync(DateTime nowUtc, int limit, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            SELECT * FROM pending_artifacts
            WHERE upload_url IS NOT NULL
              AND status IN (
                  'UPLOAD_URL_RECEIVED','upload_url_received','UploadUrlReceived',
                  'RETRY_WAIT','retry_wait','RetryWait'
              )
              AND (available_at_utc IS NULL OR available_at_utc <= $now)
            ORDER BY created_at_utc
            LIMIT $limit;
            """;
        cmd.Parameters.AddWithValue("$now", nowUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$limit", limit);
        return await ReadListAsync(cmd, ct);
    }

    public async Task SetAnnouncementAsync(string artifactId, string messageId, ArtifactStatus status, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            UPDATE pending_artifacts
            SET announcement_message_id = $message_id,
                status = CASE
                    WHEN status IN ('CONFIRMED','confirmed','FAILED','failed') THEN status
                    ELSE $status
                END
            WHERE artifact_id = $id;
            """;
        cmd.Parameters.AddWithValue("$id", artifactId);
        cmd.Parameters.AddWithValue("$message_id", messageId);
        cmd.Parameters.AddWithValue("$status", ToDbStatus(status));
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task SetUploadInstructionsAsync(
        string artifactId,
        string uploadSessionId,
        string uploadUrl,
        string uploadMethod,
        string? uploadHeadersJson,
        DateTime? uploadExpiresAtUtc,
        DateTime availableAtUtc,
        CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            UPDATE pending_artifacts
            SET upload_session_id = $upload_session_id,
                upload_url = $upload_url,
                upload_method = $upload_method,
                upload_headers_json = $upload_headers_json,
                upload_expires_at_utc = $upload_expires_at,
                available_at_utc = $available_at,
                last_error = NULL,
                status = CASE
                    WHEN status IN ('CONFIRMED','confirmed','FAILED','failed','UPLOADED','uploaded') THEN status
                    ELSE 'UPLOAD_URL_RECEIVED'
                END
            WHERE artifact_id = $id;
            """;
        cmd.Parameters.AddWithValue("$id", artifactId);
        cmd.Parameters.AddWithValue("$upload_session_id", uploadSessionId);
        cmd.Parameters.AddWithValue("$upload_url", uploadUrl);
        cmd.Parameters.AddWithValue("$upload_method", uploadMethod);
        cmd.Parameters.AddWithValue("$upload_headers_json", (object?)uploadHeadersJson ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$upload_expires_at", uploadExpiresAtUtc?.ToString("o") ?? (object)DBNull.Value);
        cmd.Parameters.AddWithValue("$available_at", availableAtUtc.ToString("o"));
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task SetUploadedMessageAsync(
        string artifactId,
        string messageId,
        ArtifactStatus status,
        DateTime uploadedAtUtc,
        string? remoteObjectId,
        string? lastError,
        CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            UPDATE pending_artifacts
            SET uploaded_message_id = COALESCE(uploaded_message_id, $message_id),
                status = $status,
                uploaded_at_utc = $uploaded,
                remote_object_id = $remote,
                last_error = $error,
                available_at_utc = NULL
            WHERE artifact_id = $id
              AND status NOT IN ('CONFIRMED','confirmed','FAILED','failed');
            """;
        cmd.Parameters.AddWithValue("$id", artifactId);
        cmd.Parameters.AddWithValue("$message_id", messageId);
        cmd.Parameters.AddWithValue("$status", ToDbStatus(status));
        cmd.Parameters.AddWithValue("$uploaded", uploadedAtUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$remote", (object?)remoteObjectId ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$error", (object?)lastError ?? DBNull.Value);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task SetFailedMessageAsync(string artifactId, string messageId, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            UPDATE pending_artifacts
            SET failed_message_id = COALESCE(failed_message_id, $message_id)
            WHERE artifact_id = $id;
            """;
        cmd.Parameters.AddWithValue("$id", artifactId);
        cmd.Parameters.AddWithValue("$message_id", messageId);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task<IReadOnlyList<PendingArtifactRecord>> GetNonFinalAsync(int limit = 100, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            SELECT * FROM pending_artifacts
            WHERE status NOT IN ('CONFIRMED','confirmed','FAILED','failed')
            ORDER BY created_at_utc DESC
            LIMIT $limit;
            """;
        cmd.Parameters.AddWithValue("$limit", limit);
        return await ReadListAsync(cmd, ct);
    }

    public async Task UpdateStatusAsync(
        string artifactId,
        ArtifactStatus status,
        DateTime? availableAtUtc,
        DateTime? uploadedAtUtc,
        DateTime? confirmedAtUtc,
        string? remoteObjectId,
        int attemptCount,
        string? lastError,
        CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            UPDATE pending_artifacts SET
                status = $status,
                available_at_utc = $available,
                uploaded_at_utc = $uploaded,
                confirmed_at_utc = $confirmed,
                remote_object_id = $remote,
                attempt_count = $attempts,
                last_error = $error
            WHERE artifact_id = $id;
            """;
        cmd.Parameters.AddWithValue("$id", artifactId);
        cmd.Parameters.AddWithValue("$status", ToDbStatus(status));
        cmd.Parameters.AddWithValue("$available", availableAtUtc?.ToString("o") ?? (object)DBNull.Value);
        cmd.Parameters.AddWithValue("$uploaded", uploadedAtUtc?.ToString("o") ?? (object)DBNull.Value);
        cmd.Parameters.AddWithValue("$confirmed", confirmedAtUtc?.ToString("o") ?? (object)DBNull.Value);
        cmd.Parameters.AddWithValue("$remote", (object?)remoteObjectId ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$attempts", attemptCount);
        cmd.Parameters.AddWithValue("$error", (object?)lastError ?? DBNull.Value);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task<PendingArtifactDiagnostics> GetDiagnosticsAsync(CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT status, COUNT(*) FROM pending_artifacts GROUP BY status;";

        var counts = new Dictionary<ArtifactStatus, int>();
        using var r = await cmd.ExecuteReaderAsync(ct);
        while (await r.ReadAsync(ct))
            counts[ParseStatus(r.GetString(0))] = r.GetInt32(1);

        return new PendingArtifactDiagnostics(
            counts.GetValueOrDefault(ArtifactStatus.Pending),
            counts.GetValueOrDefault(ArtifactStatus.Announced),
            counts.GetValueOrDefault(ArtifactStatus.UploadUrlReceived),
            counts.GetValueOrDefault(ArtifactStatus.Uploading),
            counts.GetValueOrDefault(ArtifactStatus.Uploaded),
            counts.GetValueOrDefault(ArtifactStatus.Confirmed),
            counts.GetValueOrDefault(ArtifactStatus.RetryWait),
            counts.GetValueOrDefault(ArtifactStatus.Failed));
    }

    private static async Task<IReadOnlyList<PendingArtifactRecord>> ReadListAsync(SqliteCommand cmd, CancellationToken ct)
    {
        var list = new List<PendingArtifactRecord>();
        using var r = await cmd.ExecuteReaderAsync(ct);
        while (await r.ReadAsync(ct))
            list.Add(Map(r));
        return list;
    }

    private static void BindAll(SqliteCommand cmd, PendingArtifactRecord artifact)
    {
        cmd.Parameters.AddWithValue("$id", artifact.ArtifactId);
        cmd.Parameters.AddWithValue("$eid", artifact.ExecutionId);
        cmd.Parameters.AddWithValue("$aid", artifact.ExecutionAttemptId);
        cmd.Parameters.AddWithValue("$name", artifact.Name);
        cmd.Parameters.AddWithValue("$contentType", artifact.ContentType);
        cmd.Parameters.AddWithValue("$size", artifact.SizeBytes);
        cmd.Parameters.AddWithValue("$sha", artifact.Sha256);
        cmd.Parameters.AddWithValue("$path", artifact.LocalPath);
        cmd.Parameters.AddWithValue("$status", ToDbStatus(artifact.Status));
        cmd.Parameters.AddWithValue("$kind", (object?)artifact.Kind ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$created", artifact.CreatedAtUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$available", artifact.AvailableAtUtc?.ToString("o") ?? (object)DBNull.Value);
        cmd.Parameters.AddWithValue("$uploaded", artifact.UploadedAtUtc?.ToString("o") ?? (object)DBNull.Value);
        cmd.Parameters.AddWithValue("$confirmed", artifact.ConfirmedAtUtc?.ToString("o") ?? (object)DBNull.Value);
        cmd.Parameters.AddWithValue("$remote", (object?)artifact.RemoteObjectId ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$announcementMessageId", (object?)artifact.AnnouncementMessageId ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$uploadedMessageId", (object?)artifact.UploadedMessageId ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$failedMessageId", (object?)artifact.FailedMessageId ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$uploadSessionId", (object?)artifact.UploadSessionId ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$uploadUrl", (object?)artifact.UploadUrl ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$uploadMethod", string.IsNullOrWhiteSpace(artifact.UploadMethod) ? "PUT" : artifact.UploadMethod);
        cmd.Parameters.AddWithValue("$uploadHeadersJson", (object?)artifact.UploadHeadersJson ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$uploadExpiresAt", artifact.UploadExpiresAtUtc?.ToString("o") ?? (object)DBNull.Value);
        cmd.Parameters.AddWithValue("$attempts", artifact.AttemptCount);
        cmd.Parameters.AddWithValue("$error", (object?)artifact.LastError ?? DBNull.Value);
    }

    private static PendingArtifactRecord Map(SqliteDataReader r) => new()
    {
        ArtifactId = r.GetString(r.GetOrdinal("artifact_id")),
        ExecutionId = r.GetString(r.GetOrdinal("execution_id")),
        ExecutionAttemptId = r.GetString(r.GetOrdinal("execution_attempt_id")),
        Name = r.GetString(r.GetOrdinal("name")),
        ContentType = r.GetString(r.GetOrdinal("content_type")),
        SizeBytes = r.GetInt64(r.GetOrdinal("size_bytes")),
        Sha256 = r.GetString(r.GetOrdinal("sha256")),
        LocalPath = r.GetString(r.GetOrdinal("local_path")),
        Status = ParseStatus(r.GetString(r.GetOrdinal("status"))),
        Kind = r.IsDBNull(r.GetOrdinal("kind")) ? null : r.GetString(r.GetOrdinal("kind")),
        CreatedAtUtc = ParseUtc(r.GetString(r.GetOrdinal("created_at_utc"))),
        AvailableAtUtc = r.IsDBNull(r.GetOrdinal("available_at_utc")) ? null : ParseUtc(r.GetString(r.GetOrdinal("available_at_utc"))),
        UploadedAtUtc = r.IsDBNull(r.GetOrdinal("uploaded_at_utc")) ? null : ParseUtc(r.GetString(r.GetOrdinal("uploaded_at_utc"))),
        ConfirmedAtUtc = r.IsDBNull(r.GetOrdinal("confirmed_at_utc")) ? null : ParseUtc(r.GetString(r.GetOrdinal("confirmed_at_utc"))),
        RemoteObjectId = r.IsDBNull(r.GetOrdinal("remote_object_id")) ? null : r.GetString(r.GetOrdinal("remote_object_id")),
        AnnouncementMessageId = ReadNullableString(r, "announcement_message_id"),
        UploadedMessageId = ReadNullableString(r, "uploaded_message_id"),
        FailedMessageId = ReadNullableString(r, "failed_message_id"),
        UploadSessionId = ReadNullableString(r, "upload_session_id"),
        UploadUrl = ReadNullableString(r, "upload_url"),
        UploadMethod = ReadNullableString(r, "upload_method") ?? "PUT",
        UploadHeadersJson = ReadNullableString(r, "upload_headers_json"),
        UploadExpiresAtUtc = ReadNullableDateTime(r, "upload_expires_at_utc"),
        AttemptCount = r.GetInt32(r.GetOrdinal("attempt_count")),
        LastError = r.IsDBNull(r.GetOrdinal("last_error")) ? null : r.GetString(r.GetOrdinal("last_error"))
    };

    private static string ToDbStatus(ArtifactStatus status) => status switch
    {
        ArtifactStatus.Pending => "PENDING",
        ArtifactStatus.Announced => "ANNOUNCED",
        ArtifactStatus.UploadUrlReceived => "UPLOAD_URL_RECEIVED",
        ArtifactStatus.Uploading => "UPLOADING",
        ArtifactStatus.Uploaded => "UPLOADED",
        ArtifactStatus.Confirmed => "CONFIRMED",
        ArtifactStatus.RetryWait => "RETRY_WAIT",
        ArtifactStatus.Failed => "FAILED",
        _ => "PENDING"
    };

    private static ArtifactStatus ParseStatus(string value) => value.Trim().ToUpperInvariant() switch
    {
        "PENDING" => ArtifactStatus.Pending,
        "ANNOUNCED" => ArtifactStatus.Announced,
        "UPLOAD_URL_RECEIVED" or "UPLOADURLRECEIVED" => ArtifactStatus.UploadUrlReceived,
        "UPLOADING" => ArtifactStatus.Uploading,
        "UPLOADED" => ArtifactStatus.Uploaded,
        "CONFIRMED" => ArtifactStatus.Confirmed,
        "RETRY_WAIT" or "RETRYWAIT" => ArtifactStatus.RetryWait,
        "FAILED" => ArtifactStatus.Failed,
        "CREATED" => ArtifactStatus.Pending,
        "AVAILABLE" => ArtifactStatus.Uploaded,
        "EXPIRED" => ArtifactStatus.Failed,
        _ => ArtifactStatus.Failed
    };

    private static string? ReadNullableString(SqliteDataReader r, string column)
    {
        var ordinal = r.GetOrdinal(column);
        return r.IsDBNull(ordinal) ? null : r.GetString(ordinal);
    }

    private static DateTime? ReadNullableDateTime(SqliteDataReader r, string column)
    {
        var value = ReadNullableString(r, column);
        return value is null ? null : ParseUtc(value);
    }

    private static DateTime ParseUtc(string value)
    {
        var parsed = DateTime.Parse(value, CultureInfo.InvariantCulture, DateTimeStyles.RoundtripKind);
        return parsed.Kind switch
        {
            DateTimeKind.Utc => parsed,
            DateTimeKind.Local => parsed.ToUniversalTime(),
            _ => DateTime.SpecifyKind(parsed, DateTimeKind.Utc)
        };
    }
}
