using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models;
using Biason.AutomationAgent.Infrastructure.Database;

namespace Biason.AutomationAgent.Infrastructure.Persistence;

public sealed class ExecutionRepository : IExecutionRepository
{
    private readonly SqliteDatabaseManager _db;

    public ExecutionRepository(SqliteDatabaseManager db) => _db = db;

    public async Task SaveAsync(ExecutionRecord record, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            INSERT INTO executions (execution_id, current_state, previous_state, created_at_utc, last_transition_utc,
                automation_id, automation_version_id, reason, pool, attempt_count, current_attempt_id,
                workspace_path, process_id, reservation_id, timeout_seconds, input_json)
            VALUES ($eid, $cs, $ps, $cat, $lt, $aid, $avid, $r, $pool, $ac, $caid, $wp, $pid, $rid, $ts, $ij);
            """;
        BindAll(cmd, record);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task<ExecutionRecord?> GetAsync(string executionId, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT * FROM executions WHERE execution_id = $eid;";
        cmd.Parameters.AddWithValue("$eid", executionId);
        using var reader = await cmd.ExecuteReaderAsync(ct);
        if (!await reader.ReadAsync(ct)) return null;
        return MapRecord(reader);
    }

    public async Task UpdateStateAsync(string executionId, ExecutionRecord record, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            UPDATE executions SET current_state = $cs, previous_state = $ps, last_transition_utc = $lt,
                reason = $r, attempt_count = $ac, current_attempt_id = $caid,
                workspace_path = $wp, process_id = $pid, reservation_id = $rid
            WHERE execution_id = $eid;
            """;
        cmd.Parameters.AddWithValue("$cs", record.CurrentState.ToString());
        cmd.Parameters.AddWithValue("$ps", record.PreviousState?.ToString() ?? (object)DBNull.Value);
        cmd.Parameters.AddWithValue("$lt", record.LastTransitionUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$r", (object?)record.Reason ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$ac", record.AttemptCount);
        cmd.Parameters.AddWithValue("$caid", (object?)record.CurrentAttemptId ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$wp", (object?)record.WorkspacePath ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$pid", record.ProcessId.HasValue ? record.ProcessId.Value : DBNull.Value);
        cmd.Parameters.AddWithValue("$rid", (object?)record.ReservationId ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$eid", executionId);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task<IReadOnlyList<ExecutionRecord>> GetByStateAsync(ExecutionState state, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT * FROM executions WHERE current_state = $s ORDER BY created_at_utc DESC;";
        cmd.Parameters.AddWithValue("$s", state.ToString());
        return await ReadListAsync(cmd, ct);
    }

    public async Task<IReadOnlyList<ExecutionRecord>> GetActiveAsync(CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            SELECT * FROM executions
            WHERE current_state NOT IN ('Succeeded','Rejected','Cancelled','Failed','TimedOut','Orphaned')
            ORDER BY created_at_utc DESC;
            """;
        return await ReadListAsync(cmd, ct);
    }

    public async Task<IReadOnlyList<ExecutionRecord>> GetByPoolAsync(PoolType pool, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT * FROM executions WHERE pool = $p ORDER BY created_at_utc DESC;";
        cmd.Parameters.AddWithValue("$p", pool.ToString());
        return await ReadListAsync(cmd, ct);
    }

    public async Task<int> CountByStateAsync(ExecutionState state, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT COUNT(*) FROM executions WHERE current_state = $s;";
        cmd.Parameters.AddWithValue("$s", state.ToString());
        var result = await cmd.ExecuteScalarAsync(ct);
        return Convert.ToInt32(result);
    }

    private static async Task<IReadOnlyList<ExecutionRecord>> ReadListAsync(Microsoft.Data.Sqlite.SqliteCommand cmd, CancellationToken ct)
    {
        var list = new List<ExecutionRecord>();
        using var reader = await cmd.ExecuteReaderAsync(ct);
        while (await reader.ReadAsync(ct))
            list.Add(MapRecord(reader));
        return list;
    }

    private static ExecutionRecord MapRecord(Microsoft.Data.Sqlite.SqliteDataReader reader)
    {
        return new ExecutionRecord
        {
            ExecutionId = reader.GetString(reader.GetOrdinal("execution_id")),
            CurrentState = Enum.Parse<ExecutionState>(reader.GetString(reader.GetOrdinal("current_state")), ignoreCase: true),
            PreviousState = reader.IsDBNull(reader.GetOrdinal("previous_state")) ? null : Enum.Parse<ExecutionState>(reader.GetString(reader.GetOrdinal("previous_state")), ignoreCase: true),
            CreatedAtUtc = DateTime.Parse(reader.GetString(reader.GetOrdinal("created_at_utc"))),
            LastTransitionUtc = DateTime.Parse(reader.GetString(reader.GetOrdinal("last_transition_utc"))),
            AutomationId = reader.IsDBNull(reader.GetOrdinal("automation_id")) ? null : reader.GetString(reader.GetOrdinal("automation_id")),
            AutomationVersionId = reader.IsDBNull(reader.GetOrdinal("automation_version_id")) ? null : reader.GetString(reader.GetOrdinal("automation_version_id")),
            Reason = reader.IsDBNull(reader.GetOrdinal("reason")) ? null : reader.GetString(reader.GetOrdinal("reason")),
            Pool = reader.IsDBNull(reader.GetOrdinal("pool")) ? null : Enum.Parse<PoolType>(reader.GetString(reader.GetOrdinal("pool")), ignoreCase: true),
            AttemptCount = reader.IsDBNull(reader.GetOrdinal("attempt_count")) ? 0 : reader.GetInt32(reader.GetOrdinal("attempt_count")),
            CurrentAttemptId = reader.IsDBNull(reader.GetOrdinal("current_attempt_id")) ? null : reader.GetString(reader.GetOrdinal("current_attempt_id")),
            WorkspacePath = reader.IsDBNull(reader.GetOrdinal("workspace_path")) ? null : reader.GetString(reader.GetOrdinal("workspace_path")),
            ProcessId = reader.IsDBNull(reader.GetOrdinal("process_id")) ? null : reader.GetInt32(reader.GetOrdinal("process_id")),
            ReservationId = reader.IsDBNull(reader.GetOrdinal("reservation_id")) ? null : reader.GetString(reader.GetOrdinal("reservation_id")),
            TimeoutSeconds = reader.IsDBNull(reader.GetOrdinal("timeout_seconds")) ? null : reader.GetInt32(reader.GetOrdinal("timeout_seconds")),
            InputJson = reader.IsDBNull(reader.GetOrdinal("input_json")) ? null : reader.GetString(reader.GetOrdinal("input_json"))
        };
    }

    private static void BindAll(Microsoft.Data.Sqlite.SqliteCommand cmd, ExecutionRecord r)
    {
        cmd.Parameters.AddWithValue("$eid", r.ExecutionId);
        cmd.Parameters.AddWithValue("$cs", r.CurrentState.ToString());
        cmd.Parameters.AddWithValue("$ps", r.PreviousState?.ToString() ?? (object)DBNull.Value);
        cmd.Parameters.AddWithValue("$cat", r.CreatedAtUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$lt", r.LastTransitionUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$aid", (object?)r.AutomationId ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$avid", (object?)r.AutomationVersionId ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$r", (object?)r.Reason ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$pool", r.Pool?.ToString() ?? (object)DBNull.Value);
        cmd.Parameters.AddWithValue("$ac", r.AttemptCount);
        cmd.Parameters.AddWithValue("$caid", (object?)r.CurrentAttemptId ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$wp", (object?)r.WorkspacePath ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$pid", r.ProcessId.HasValue ? r.ProcessId.Value : DBNull.Value);
        cmd.Parameters.AddWithValue("$rid", (object?)r.ReservationId ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$ts", r.TimeoutSeconds.HasValue ? r.TimeoutSeconds.Value : DBNull.Value);
        cmd.Parameters.AddWithValue("$ij", (object?)r.InputJson ?? DBNull.Value);
    }
}
