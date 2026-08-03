using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Models.Messaging;
using Biason.AutomationAgent.Infrastructure.Database;

namespace Biason.AutomationAgent.Infrastructure.Persistence;

public sealed class OutboxRepository : IOutboxRepository
{
    private readonly SqliteDatabaseManager _db;

    public OutboxRepository(SqliteDatabaseManager db) => _db = db;

    public async Task<OutboxMessage> EnqueueAsync(OutboxMessageDraft draft, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            INSERT OR IGNORE INTO outbox_events
                (event_type, payload_json, created_at_utc, retry_count,
                 message_id, message_type, agent_id, execution_id, execution_attempt_id,
                 sequence, available_at_utc, attempt_count, status, payload_size_bytes, last_error)
            VALUES
                ($event_type, $payload_json, $created_at_utc, 0,
                 $message_id, $message_type, $agent_id, $execution_id, $execution_attempt_id,
                 $sequence, $available_at_utc, 0, $status, $payload_size_bytes, $last_error);
            """;
        cmd.Parameters.AddWithValue("$event_type", draft.MessageType);
        cmd.Parameters.AddWithValue("$payload_json", draft.PayloadJson);
        cmd.Parameters.AddWithValue("$created_at_utc", draft.CreatedAtUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$message_id", draft.MessageId);
        cmd.Parameters.AddWithValue("$message_type", draft.MessageType);
        cmd.Parameters.AddWithValue("$agent_id", (object?)draft.AgentId ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$execution_id", (object?)draft.ExecutionId ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$execution_attempt_id", (object?)draft.ExecutionAttemptId ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$sequence", (object?)draft.Sequence ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$available_at_utc", draft.AvailableAtUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$status", draft.Status);
        cmd.Parameters.AddWithValue("$payload_size_bytes", draft.PayloadSizeBytes);
        cmd.Parameters.AddWithValue("$last_error", (object?)draft.LastError ?? DBNull.Value);
        await cmd.ExecuteNonQueryAsync(ct);

        return await GetByMessageIdAsync(draft.MessageId, ct)
            ?? throw new InvalidOperationException($"Outbox message {draft.MessageId} was not persisted.");
    }

    public async Task<OutboxMessage?> GetByMessageIdAsync(string messageId, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT * FROM outbox_events WHERE message_id = $message_id;";
        cmd.Parameters.AddWithValue("$message_id", messageId);
        return await ReadSingleAsync(cmd, ct);
    }

    public async Task<IReadOnlyList<OutboxMessage>> GetReadyBatchAsync(int maxCount, DateTime nowUtc, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            SELECT *
            FROM outbox_events e
            WHERE e.message_id IS NOT NULL
              AND e.message_type IS NOT NULL
              AND e.status IN ('pending', 'failed')
              AND (e.available_at_utc IS NULL OR e.available_at_utc <= $now)
              AND NOT EXISTS (
                  SELECT 1
                  FROM outbox_events prev
                  WHERE e.execution_attempt_id IS NOT NULL
                    AND e.sequence IS NOT NULL
                    AND prev.execution_attempt_id = e.execution_attempt_id
                    AND prev.sequence IS NOT NULL
                    AND prev.sequence < e.sequence
                    AND prev.status NOT IN ('acknowledged', 'dead_letter')
              )
            ORDER BY
                CASE WHEN e.execution_attempt_id IS NULL THEN 1 ELSE 0 END,
                e.execution_attempt_id,
                COALESCE(e.sequence, e.id),
                e.id
            LIMIT $limit;
            """;
        cmd.Parameters.AddWithValue("$now", nowUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$limit", maxCount);
        return await ReadListAsync(cmd, ct);
    }

    public async Task MarkSentAsync(long id, DateTime sentAtUtc, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            UPDATE outbox_events
            SET status = 'sent',
                sent_at_utc = $sent_at,
                last_attempt_at_utc = $sent_at,
                attempt_count = attempt_count + 1,
                retry_count = retry_count + 1,
                last_error = NULL
            WHERE id = $id AND status <> 'acknowledged';
            """;
        cmd.Parameters.AddWithValue("$id", id);
        cmd.Parameters.AddWithValue("$sent_at", sentAtUtc.ToString("o"));
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task MarkFailedAsync(long id, DateTime availableAtUtc, string error, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            UPDATE outbox_events
            SET status = 'failed',
                available_at_utc = $available_at,
                last_error = $error
            WHERE id = $id AND status NOT IN ('acknowledged', 'dead_letter');
            """;
        cmd.Parameters.AddWithValue("$id", id);
        cmd.Parameters.AddWithValue("$available_at", availableAtUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$error", error);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task MarkDeadLetterAsync(long id, DateTime nowUtc, string error, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            UPDATE outbox_events
            SET status = 'dead_letter',
                available_at_utc = NULL,
                last_attempt_at_utc = $now,
                last_error = $error
            WHERE id = $id AND status <> 'acknowledged';
            """;
        cmd.Parameters.AddWithValue("$id", id);
        cmd.Parameters.AddWithValue("$now", nowUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$error", error);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task MarkAcknowledgedAsync(string messageId, DateTime acknowledgedAtUtc, string? detail = null, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            UPDATE outbox_events
            SET status = 'acknowledged',
                acknowledged_at_utc = $acknowledged_at,
                last_error = $detail
            WHERE message_id = $message_id;
            """;
        cmd.Parameters.AddWithValue("$message_id", messageId);
        cmd.Parameters.AddWithValue("$acknowledged_at", acknowledgedAtUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$detail", (object?)detail ?? DBNull.Value);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task<int> MarkAcknowledgedThroughSequenceAsync(
        string executionAttemptId,
        long lastContiguousSequence,
        DateTime acknowledgedAtUtc,
        string? detail = null,
        CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            UPDATE outbox_events
            SET status = 'acknowledged',
                acknowledged_at_utc = $acknowledged_at,
                last_error = $detail
            WHERE execution_attempt_id = $attempt_id
              AND sequence IS NOT NULL
              AND sequence <= $sequence
              AND status <> 'dead_letter';
            """;
        cmd.Parameters.AddWithValue("$attempt_id", executionAttemptId);
        cmd.Parameters.AddWithValue("$sequence", lastContiguousSequence);
        cmd.Parameters.AddWithValue("$acknowledged_at", acknowledgedAtUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$detail", (object?)detail ?? DBNull.Value);
        return await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task<int> RecoverTimedOutAsync(DateTime nowUtc, TimeSpan acknowledgementTimeout, int maxAttempts, CancellationToken ct = default)
    {
        var deadline = nowUtc - acknowledgementTimeout;

        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            UPDATE outbox_events
            SET status = CASE
                    WHEN attempt_count >= $max_attempts THEN 'dead_letter'
                    ELSE 'failed'
                END,
                available_at_utc = CASE
                    WHEN attempt_count >= $max_attempts THEN NULL
                    ELSE $now
                END,
                last_error = CASE
                    WHEN attempt_count >= $max_attempts THEN 'ACK not received after max attempts'
                    ELSE 'ACK timeout; scheduled for replay'
                END
            WHERE status IN ('sent', 'sending')
              AND (sent_at_utc IS NULL OR sent_at_utc <= $deadline);
            """;
        cmd.Parameters.AddWithValue("$now", nowUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$deadline", deadline.ToString("o"));
        cmd.Parameters.AddWithValue("$max_attempts", maxAttempts);
        return await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task<int> CountPendingAsync(CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            SELECT COUNT(*)
            FROM outbox_events
            WHERE status IN ('pending', 'failed', 'sent')
              AND message_id IS NOT NULL;
            """;
        return Convert.ToInt32(await cmd.ExecuteScalarAsync(ct));
    }

    public async Task<OutboxDiagnostics> GetDiagnosticsAsync(CancellationToken ct = default)
    {
        var counts = await CountByStatusAsync(ct);
        return new OutboxDiagnostics
        {
            Pending = Get(counts, OutboxMessageStatus.Pending),
            Failed = Get(counts, OutboxMessageStatus.Failed),
            Sent = Get(counts, OutboxMessageStatus.Sent),
            Acknowledged = Get(counts, OutboxMessageStatus.Acknowledged),
            DeadLetter = Get(counts, OutboxMessageStatus.DeadLetter)
        };
    }

    private async Task<Dictionary<string, int>> CountByStatusAsync(CancellationToken ct)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT status, COUNT(*) FROM outbox_events GROUP BY status;";
        var result = new Dictionary<string, int>(StringComparer.Ordinal);
        using var reader = await cmd.ExecuteReaderAsync(ct);
        while (await reader.ReadAsync(ct))
            result[reader.GetString(0)] = Convert.ToInt32(reader.GetInt64(1));
        return result;
    }

    private static int Get(Dictionary<string, int> counts, string status) =>
        counts.TryGetValue(status, out var value) ? value : 0;

    private static async Task<OutboxMessage?> ReadSingleAsync(Microsoft.Data.Sqlite.SqliteCommand cmd, CancellationToken ct)
    {
        using var reader = await cmd.ExecuteReaderAsync(ct);
        return await reader.ReadAsync(ct) ? Map(reader) : null;
    }

    private static async Task<IReadOnlyList<OutboxMessage>> ReadListAsync(Microsoft.Data.Sqlite.SqliteCommand cmd, CancellationToken ct)
    {
        var list = new List<OutboxMessage>();
        using var reader = await cmd.ExecuteReaderAsync(ct);
        while (await reader.ReadAsync(ct))
            list.Add(Map(reader));
        return list;
    }

    private static OutboxMessage Map(Microsoft.Data.Sqlite.SqliteDataReader r) => new()
    {
        Id = r.GetInt64(r.GetOrdinal("id")),
        MessageId = r.GetString(r.GetOrdinal("message_id")),
        MessageType = r.GetString(r.GetOrdinal("message_type")),
        PayloadJson = r.GetString(r.GetOrdinal("payload_json")),
        AgentId = ReadString(r, "agent_id"),
        ExecutionId = ReadString(r, "execution_id"),
        ExecutionAttemptId = ReadString(r, "execution_attempt_id"),
        Sequence = r.IsDBNull(r.GetOrdinal("sequence")) ? null : r.GetInt64(r.GetOrdinal("sequence")),
        CreatedAtUtc = DateTime.Parse(r.GetString(r.GetOrdinal("created_at_utc"))),
        AvailableAtUtc = ReadDateTime(r, "available_at_utc"),
        SentAtUtc = ReadDateTime(r, "sent_at_utc"),
        AcknowledgedAtUtc = ReadDateTime(r, "acknowledged_at_utc"),
        AttemptCount = r.GetInt32(r.GetOrdinal("attempt_count")),
        Status = r.GetString(r.GetOrdinal("status")),
        PayloadSizeBytes = r.GetInt32(r.GetOrdinal("payload_size_bytes")),
        LastError = ReadString(r, "last_error")
    };

    private static string? ReadString(Microsoft.Data.Sqlite.SqliteDataReader r, string column)
    {
        var ordinal = r.GetOrdinal(column);
        return r.IsDBNull(ordinal) ? null : r.GetString(ordinal);
    }

    private static DateTime? ReadDateTime(Microsoft.Data.Sqlite.SqliteDataReader r, string column)
    {
        var value = ReadString(r, column);
        return value is null ? null : DateTime.Parse(value);
    }
}
