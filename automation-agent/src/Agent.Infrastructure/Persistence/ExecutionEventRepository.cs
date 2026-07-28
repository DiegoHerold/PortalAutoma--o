using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Models.Execution;
using Biason.AutomationAgent.Infrastructure.Database;

namespace Biason.AutomationAgent.Infrastructure.Persistence;

public sealed class ExecutionEventRepository : IExecutionEventRepository
{
    private readonly SqliteDatabaseManager _db;
    public ExecutionEventRepository(SqliteDatabaseManager db) => _db = db;

    public async Task SaveAsync(ExecutionEvent evt, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            INSERT INTO execution_events (execution_id, attempt_id, event_type, message, data_json, occurred_at_utc)
            VALUES ($eid, $aid, $et, $m, $d, $o);
            """;
        cmd.Parameters.AddWithValue("$eid", evt.ExecutionId);
        cmd.Parameters.AddWithValue("$aid", evt.AttemptId);
        cmd.Parameters.AddWithValue("$et", evt.EventType);
        cmd.Parameters.AddWithValue("$m", (object?)evt.Message ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$d", (object?)evt.DataJson ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$o", evt.OccurredAtUtc.ToString("o"));
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task SaveBatchAsync(IEnumerable<ExecutionEvent> events, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var tx = conn.BeginTransaction();
        foreach (var evt in events)
        {
            using var cmd = conn.CreateCommand();
            cmd.Transaction = tx;
            cmd.CommandText = """
                INSERT INTO execution_events (execution_id, attempt_id, event_type, message, data_json, occurred_at_utc)
                VALUES ($eid, $aid, $et, $m, $d, $o);
                """;
            cmd.Parameters.AddWithValue("$eid", evt.ExecutionId);
            cmd.Parameters.AddWithValue("$aid", evt.AttemptId);
            cmd.Parameters.AddWithValue("$et", evt.EventType);
            cmd.Parameters.AddWithValue("$m", (object?)evt.Message ?? DBNull.Value);
            cmd.Parameters.AddWithValue("$d", (object?)evt.DataJson ?? DBNull.Value);
            cmd.Parameters.AddWithValue("$o", evt.OccurredAtUtc.ToString("o"));
            await cmd.ExecuteNonQueryAsync(ct);
        }
        tx.Commit();
    }

    public async Task<IReadOnlyList<ExecutionEvent>> GetByExecutionAsync(string executionId, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT * FROM execution_events WHERE execution_id = $eid ORDER BY occurred_at_utc;";
        cmd.Parameters.AddWithValue("$eid", executionId);
        return await ReadListAsync(cmd, ct);
    }

    public async Task<IReadOnlyList<ExecutionEvent>> GetByAttemptAsync(string attemptId, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT * FROM execution_events WHERE attempt_id = $aid ORDER BY occurred_at_utc;";
        cmd.Parameters.AddWithValue("$aid", attemptId);
        return await ReadListAsync(cmd, ct);
    }

    private static async Task<IReadOnlyList<ExecutionEvent>> ReadListAsync(Microsoft.Data.Sqlite.SqliteCommand cmd, CancellationToken ct)
    {
        var list = new List<ExecutionEvent>();
        using var r = await cmd.ExecuteReaderAsync(ct);
        while (await r.ReadAsync(ct))
        {
            list.Add(new ExecutionEvent
            {
                Id = r.GetInt64(r.GetOrdinal("id")),
                ExecutionId = r.GetString(r.GetOrdinal("execution_id")),
                AttemptId = r.GetString(r.GetOrdinal("attempt_id")),
                EventType = r.GetString(r.GetOrdinal("event_type")),
                Message = r.IsDBNull(r.GetOrdinal("message")) ? null : r.GetString(r.GetOrdinal("message")),
                DataJson = r.IsDBNull(r.GetOrdinal("data_json")) ? null : r.GetString(r.GetOrdinal("data_json")),
                OccurredAtUtc = DateTime.Parse(r.GetString(r.GetOrdinal("occurred_at_utc")))
            });
        }
        return list;
    }
}
