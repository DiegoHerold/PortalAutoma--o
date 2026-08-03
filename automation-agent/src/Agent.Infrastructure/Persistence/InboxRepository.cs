using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Models.Messaging;
using Biason.AutomationAgent.Infrastructure.Database;

namespace Biason.AutomationAgent.Infrastructure.Persistence;

public sealed class InboxRepository : IInboxRepository
{
    private readonly SqliteDatabaseManager _db;

    public InboxRepository(SqliteDatabaseManager db) => _db = db;

    public async Task<InboxStoreResult> StoreReceivedAsync(InboxCommandDraft draft, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            INSERT OR IGNORE INTO inbox_commands
                (command_type, payload_json, received_at_utc, status,
                 message_id, correlation_id, execution_id, execution_attempt_id)
            VALUES
                ($command_type, $payload_json, $received_at, 'pending',
                 $message_id, $correlation_id, $execution_id, $execution_attempt_id);
            """;
        cmd.Parameters.AddWithValue("$command_type", draft.CommandType);
        cmd.Parameters.AddWithValue("$payload_json", draft.PayloadJson);
        cmd.Parameters.AddWithValue("$received_at", draft.ReceivedAtUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$message_id", draft.MessageId);
        cmd.Parameters.AddWithValue("$correlation_id", (object?)draft.CorrelationId ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$execution_id", (object?)draft.ExecutionId ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$execution_attempt_id", (object?)draft.ExecutionAttemptId ?? DBNull.Value);
        var inserted = await cmd.ExecuteNonQueryAsync(ct) > 0;

        var command = await GetByMessageIdAsync(draft.MessageId, ct)
            ?? throw new InvalidOperationException($"Inbox command {draft.MessageId} was not persisted.");

        return new InboxStoreResult(command, IsDuplicate: !inserted, PayloadMatches: command.PayloadJson == draft.PayloadJson);
    }

    public async Task<InboxCommand?> GetByMessageIdAsync(string messageId, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT * FROM inbox_commands WHERE message_id = $message_id;";
        cmd.Parameters.AddWithValue("$message_id", messageId);
        return await ReadSingleAsync(cmd, ct);
    }

    public async Task<IReadOnlyList<InboxCommand>> GetPendingBatchAsync(int maxCount, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            SELECT *
            FROM inbox_commands
            WHERE status = 'pending'
              AND message_id IS NOT NULL
            ORDER BY received_at_utc, id
            LIMIT $limit;
            """;
        cmd.Parameters.AddWithValue("$limit", maxCount);
        return await ReadListAsync(cmd, ct);
    }

    public async Task MarkProcessingAsync(long id, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            UPDATE inbox_commands
            SET status = 'processing',
                attempt_count = attempt_count + 1
            WHERE id = $id AND status = 'pending';
            """;
        cmd.Parameters.AddWithValue("$id", id);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task MarkProcessedAsync(long id, DateTime processedAtUtc, string? result, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            UPDATE inbox_commands
            SET status = 'processed',
                processed_at_utc = $processed_at,
                result = $result,
                error = NULL
            WHERE id = $id;
            """;
        cmd.Parameters.AddWithValue("$id", id);
        cmd.Parameters.AddWithValue("$processed_at", processedAtUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$result", (object?)result ?? DBNull.Value);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task MarkPendingAsync(long id, string error, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            UPDATE inbox_commands
            SET status = 'pending',
                error = $error
            WHERE id = $id AND status = 'processing';
            """;
        cmd.Parameters.AddWithValue("$id", id);
        cmd.Parameters.AddWithValue("$error", error);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task MarkDeadLetterAsync(long id, DateTime nowUtc, string error, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            UPDATE inbox_commands
            SET status = 'dead_letter',
                processed_at_utc = $processed_at,
                error = $error
            WHERE id = $id;
            """;
        cmd.Parameters.AddWithValue("$id", id);
        cmd.Parameters.AddWithValue("$processed_at", nowUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$error", error);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task<int> CountPendingAsync(CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT COUNT(*) FROM inbox_commands WHERE status IN ('pending', 'processing');";
        return Convert.ToInt32(await cmd.ExecuteScalarAsync(ct));
    }

    public async Task<InboxDiagnostics> GetDiagnosticsAsync(CancellationToken ct = default)
    {
        var counts = await CountByStatusAsync(ct);
        return new InboxDiagnostics
        {
            Pending = Get(counts, InboxCommandStatus.Pending),
            Processing = Get(counts, InboxCommandStatus.Processing),
            Processed = Get(counts, InboxCommandStatus.Processed),
            DeadLetter = Get(counts, InboxCommandStatus.DeadLetter)
        };
    }

    private async Task<Dictionary<string, int>> CountByStatusAsync(CancellationToken ct)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT status, COUNT(*) FROM inbox_commands GROUP BY status;";
        var result = new Dictionary<string, int>(StringComparer.Ordinal);
        using var reader = await cmd.ExecuteReaderAsync(ct);
        while (await reader.ReadAsync(ct))
            result[reader.GetString(0)] = Convert.ToInt32(reader.GetInt64(1));
        return result;
    }

    private static int Get(Dictionary<string, int> counts, string status) =>
        counts.TryGetValue(status, out var value) ? value : 0;

    private static async Task<InboxCommand?> ReadSingleAsync(Microsoft.Data.Sqlite.SqliteCommand cmd, CancellationToken ct)
    {
        using var reader = await cmd.ExecuteReaderAsync(ct);
        return await reader.ReadAsync(ct) ? Map(reader) : null;
    }

    private static async Task<IReadOnlyList<InboxCommand>> ReadListAsync(Microsoft.Data.Sqlite.SqliteCommand cmd, CancellationToken ct)
    {
        var list = new List<InboxCommand>();
        using var reader = await cmd.ExecuteReaderAsync(ct);
        while (await reader.ReadAsync(ct))
            list.Add(Map(reader));
        return list;
    }

    private static InboxCommand Map(Microsoft.Data.Sqlite.SqliteDataReader r) => new()
    {
        Id = r.GetInt64(r.GetOrdinal("id")),
        MessageId = r.GetString(r.GetOrdinal("message_id")),
        CommandType = r.GetString(r.GetOrdinal("command_type")),
        PayloadJson = r.GetString(r.GetOrdinal("payload_json")),
        CorrelationId = ReadString(r, "correlation_id"),
        ExecutionId = ReadString(r, "execution_id"),
        ExecutionAttemptId = ReadString(r, "execution_attempt_id"),
        ReceivedAtUtc = DateTime.Parse(r.GetString(r.GetOrdinal("received_at_utc"))),
        ProcessedAtUtc = ReadDateTime(r, "processed_at_utc"),
        Status = r.GetString(r.GetOrdinal("status")),
        AttemptCount = r.GetInt32(r.GetOrdinal("attempt_count")),
        Result = ReadString(r, "result"),
        Error = ReadString(r, "error")
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
