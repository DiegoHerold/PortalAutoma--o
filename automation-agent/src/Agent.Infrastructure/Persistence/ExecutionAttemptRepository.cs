using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Execution;
using Biason.AutomationAgent.Infrastructure.Database;

namespace Biason.AutomationAgent.Infrastructure.Persistence;

public sealed class ExecutionAttemptRepository : IExecutionAttemptRepository
{
    private readonly SqliteDatabaseManager _db;
    public ExecutionAttemptRepository(SqliteDatabaseManager db) => _db = db;

    public async Task SaveAsync(ExecutionAttempt attempt, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            INSERT INTO execution_attempts (attempt_id, execution_id, attempt_number, current_state, pool, workspace_path, process_id, runtime_id, package_id, created_at_utc, started_at_utc, completed_at_utc, exit_code, error_message, peak_memory_mb, cpu_time_seconds)
            VALUES ($aid, $eid, $an, $cs, $p, $wp, $pid, $rid, $pkid, $cat, $sat, $caat, $ec, $em, $pm, $ct);
            """;
        BindAll(cmd, attempt);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task<ExecutionAttempt?> GetAsync(string attemptId, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT * FROM execution_attempts WHERE attempt_id = $aid;";
        cmd.Parameters.AddWithValue("$aid", attemptId);
        using var r = await cmd.ExecuteReaderAsync(ct);
        if (!await r.ReadAsync(ct)) return null;
        return Map(r);
    }

    public async Task<IReadOnlyList<ExecutionAttempt>> GetByExecutionAsync(string executionId, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT * FROM execution_attempts WHERE execution_id = $eid ORDER BY attempt_number;";
        cmd.Parameters.AddWithValue("$eid", executionId);
        var list = new List<ExecutionAttempt>();
        using var r = await cmd.ExecuteReaderAsync(ct);
        while (await r.ReadAsync(ct)) list.Add(Map(r));
        return list;
    }

    public async Task UpdateAsync(ExecutionAttempt attempt, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            UPDATE execution_attempts SET current_state=$cs, process_id=$pid, started_at_utc=$sat, completed_at_utc=$caat, exit_code=$ec, error_message=$em, peak_memory_mb=$pm, cpu_time_seconds=$ct
            WHERE attempt_id = $aid;
            """;
        cmd.Parameters.AddWithValue("$cs", attempt.CurrentState.ToString());
        cmd.Parameters.AddWithValue("$pid", attempt.ProcessId.HasValue ? attempt.ProcessId.Value : DBNull.Value);
        cmd.Parameters.AddWithValue("$sat", attempt.StartedAtUtc?.ToString("o") ?? (object)DBNull.Value);
        cmd.Parameters.AddWithValue("$caat", attempt.CompletedAtUtc?.ToString("o") ?? (object)DBNull.Value);
        cmd.Parameters.AddWithValue("$ec", attempt.ExitCode.HasValue ? attempt.ExitCode.Value : DBNull.Value);
        cmd.Parameters.AddWithValue("$em", (object?)attempt.ErrorMessage ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$pm", attempt.PeakMemoryMb.HasValue ? attempt.PeakMemoryMb.Value : DBNull.Value);
        cmd.Parameters.AddWithValue("$ct", attempt.CpuTimeSeconds.HasValue ? attempt.CpuTimeSeconds.Value : DBNull.Value);
        cmd.Parameters.AddWithValue("$aid", attempt.AttemptId);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    private static void BindAll(Microsoft.Data.Sqlite.SqliteCommand cmd, ExecutionAttempt a)
    {
        cmd.Parameters.AddWithValue("$aid", a.AttemptId);
        cmd.Parameters.AddWithValue("$eid", a.ExecutionId);
        cmd.Parameters.AddWithValue("$an", a.AttemptNumber);
        cmd.Parameters.AddWithValue("$cs", a.CurrentState.ToString());
        cmd.Parameters.AddWithValue("$p", a.Pool.ToString());
        cmd.Parameters.AddWithValue("$wp", (object?)a.WorkspacePath ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$pid", a.ProcessId.HasValue ? a.ProcessId.Value : DBNull.Value);
        cmd.Parameters.AddWithValue("$rid", (object?)a.RuntimeId ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$pkid", (object?)a.PackageId ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$cat", a.CreatedAtUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$sat", a.StartedAtUtc?.ToString("o") ?? (object)DBNull.Value);
        cmd.Parameters.AddWithValue("$caat", a.CompletedAtUtc?.ToString("o") ?? (object)DBNull.Value);
        cmd.Parameters.AddWithValue("$ec", a.ExitCode.HasValue ? a.ExitCode.Value : DBNull.Value);
        cmd.Parameters.AddWithValue("$em", (object?)a.ErrorMessage ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$pm", a.PeakMemoryMb.HasValue ? a.PeakMemoryMb.Value : DBNull.Value);
        cmd.Parameters.AddWithValue("$ct", a.CpuTimeSeconds.HasValue ? a.CpuTimeSeconds.Value : DBNull.Value);
    }

    private static ExecutionAttempt Map(Microsoft.Data.Sqlite.SqliteDataReader r) => new()
    {
        AttemptId = r.GetString(r.GetOrdinal("attempt_id")),
        ExecutionId = r.GetString(r.GetOrdinal("execution_id")),
        AttemptNumber = r.GetInt32(r.GetOrdinal("attempt_number")),
        CurrentState = Enum.Parse<ExecutionState>(r.GetString(r.GetOrdinal("current_state")), true),
        Pool = Enum.Parse<PoolType>(r.GetString(r.GetOrdinal("pool")), true),
        WorkspacePath = r.IsDBNull(r.GetOrdinal("workspace_path")) ? null : r.GetString(r.GetOrdinal("workspace_path")),
        ProcessId = r.IsDBNull(r.GetOrdinal("process_id")) ? null : r.GetInt32(r.GetOrdinal("process_id")),
        RuntimeId = r.IsDBNull(r.GetOrdinal("runtime_id")) ? null : r.GetString(r.GetOrdinal("runtime_id")),
        PackageId = r.IsDBNull(r.GetOrdinal("package_id")) ? null : r.GetString(r.GetOrdinal("package_id")),
        CreatedAtUtc = DateTime.Parse(r.GetString(r.GetOrdinal("created_at_utc"))),
        StartedAtUtc = r.IsDBNull(r.GetOrdinal("started_at_utc")) ? null : DateTime.Parse(r.GetString(r.GetOrdinal("started_at_utc"))),
        CompletedAtUtc = r.IsDBNull(r.GetOrdinal("completed_at_utc")) ? null : DateTime.Parse(r.GetString(r.GetOrdinal("completed_at_utc"))),
        ExitCode = r.IsDBNull(r.GetOrdinal("exit_code")) ? null : r.GetInt32(r.GetOrdinal("exit_code")),
        ErrorMessage = r.IsDBNull(r.GetOrdinal("error_message")) ? null : r.GetString(r.GetOrdinal("error_message")),
        PeakMemoryMb = r.IsDBNull(r.GetOrdinal("peak_memory_mb")) ? null : r.GetInt64(r.GetOrdinal("peak_memory_mb")),
        CpuTimeSeconds = r.IsDBNull(r.GetOrdinal("cpu_time_seconds")) ? null : r.GetDouble(r.GetOrdinal("cpu_time_seconds"))
    };
}
