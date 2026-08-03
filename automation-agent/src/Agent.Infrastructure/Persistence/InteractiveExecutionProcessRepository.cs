using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Models.Interactive;
using Biason.AutomationAgent.Infrastructure.Database;
using Microsoft.Data.Sqlite;

namespace Biason.AutomationAgent.Infrastructure.Persistence;

public sealed class InteractiveExecutionProcessRepository : IInteractiveExecutionProcessRepository
{
    private readonly SqliteDatabaseManager _db;
    public InteractiveExecutionProcessRepository(SqliteDatabaseManager db) => _db = db;

    public async Task AddAsync(InteractiveExecutionProcessRecord process, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            INSERT INTO interactive_execution_processes (
                execution_id, execution_attempt_id, process_id, parent_process_id, session_id,
                process_path, process_owner, started_at_utc, observed_at_utc, exited_at_utc,
                exit_code, kind, status)
            VALUES ($eid, $aid, $pid, $ppid, $sid, $path, $owner, $started, $observed, $exited, $exit, $kind, $status);
            """;
        Bind(cmd, process);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task<IReadOnlyList<InteractiveExecutionProcessRecord>> GetByAttemptAsync(string executionId, string attemptId, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT * FROM interactive_execution_processes WHERE execution_id = $eid AND execution_attempt_id = $aid ORDER BY observed_at_utc;";
        cmd.Parameters.AddWithValue("$eid", executionId);
        cmd.Parameters.AddWithValue("$aid", attemptId);
        return await ReadListAsync(cmd, ct);
    }

    public async Task<IReadOnlyList<InteractiveExecutionProcessRecord>> GetAllAsync(CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT * FROM interactive_execution_processes ORDER BY observed_at_utc DESC;";
        return await ReadListAsync(cmd, ct);
    }

    public async Task MarkExitedAsync(string executionId, string attemptId, int processId, DateTime exitedAtUtc, int? exitCode, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            UPDATE interactive_execution_processes
            SET exited_at_utc = $exited, exit_code = $exit, status = 'exited'
            WHERE execution_id = $eid AND execution_attempt_id = $aid AND process_id = $pid;
            """;
        cmd.Parameters.AddWithValue("$exited", exitedAtUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$exit", exitCode.HasValue ? exitCode.Value : DBNull.Value);
        cmd.Parameters.AddWithValue("$eid", executionId);
        cmd.Parameters.AddWithValue("$aid", attemptId);
        cmd.Parameters.AddWithValue("$pid", processId);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    private static void Bind(SqliteCommand cmd, InteractiveExecutionProcessRecord p)
    {
        cmd.Parameters.AddWithValue("$eid", p.ExecutionId);
        cmd.Parameters.AddWithValue("$aid", p.AttemptId);
        cmd.Parameters.AddWithValue("$pid", p.ProcessId);
        cmd.Parameters.AddWithValue("$ppid", p.ParentProcessId.HasValue ? p.ParentProcessId.Value : DBNull.Value);
        cmd.Parameters.AddWithValue("$sid", p.SessionId.HasValue ? p.SessionId.Value : DBNull.Value);
        cmd.Parameters.AddWithValue("$path", (object?)p.ProcessPath ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$owner", (object?)p.ProcessOwner ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$started", p.StartedAtUtc?.ToString("o") ?? (object)DBNull.Value);
        cmd.Parameters.AddWithValue("$observed", p.ObservedAtUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$exited", p.ExitedAtUtc?.ToString("o") ?? (object)DBNull.Value);
        cmd.Parameters.AddWithValue("$exit", p.ExitCode.HasValue ? p.ExitCode.Value : DBNull.Value);
        cmd.Parameters.AddWithValue("$kind", p.Kind);
        cmd.Parameters.AddWithValue("$status", p.Status);
    }

    private static async Task<IReadOnlyList<InteractiveExecutionProcessRecord>> ReadListAsync(SqliteCommand cmd, CancellationToken ct)
    {
        var list = new List<InteractiveExecutionProcessRecord>();
        using var r = await cmd.ExecuteReaderAsync(ct);
        while (await r.ReadAsync(ct))
        {
            list.Add(new InteractiveExecutionProcessRecord
            {
                Id = r.GetInt64(r.GetOrdinal("id")),
                ExecutionId = r.GetString(r.GetOrdinal("execution_id")),
                AttemptId = r.GetString(r.GetOrdinal("execution_attempt_id")),
                ProcessId = r.GetInt32(r.GetOrdinal("process_id")),
                ParentProcessId = r.IsDBNull(r.GetOrdinal("parent_process_id")) ? null : r.GetInt32(r.GetOrdinal("parent_process_id")),
                SessionId = r.IsDBNull(r.GetOrdinal("session_id")) ? null : r.GetInt32(r.GetOrdinal("session_id")),
                ProcessPath = r.IsDBNull(r.GetOrdinal("process_path")) ? null : r.GetString(r.GetOrdinal("process_path")),
                ProcessOwner = r.IsDBNull(r.GetOrdinal("process_owner")) ? null : r.GetString(r.GetOrdinal("process_owner")),
                StartedAtUtc = r.IsDBNull(r.GetOrdinal("started_at_utc")) ? null : DateTime.Parse(r.GetString(r.GetOrdinal("started_at_utc"))),
                ObservedAtUtc = DateTime.Parse(r.GetString(r.GetOrdinal("observed_at_utc"))),
                ExitedAtUtc = r.IsDBNull(r.GetOrdinal("exited_at_utc")) ? null : DateTime.Parse(r.GetString(r.GetOrdinal("exited_at_utc"))),
                ExitCode = r.IsDBNull(r.GetOrdinal("exit_code")) ? null : r.GetInt32(r.GetOrdinal("exit_code")),
                Kind = r.GetString(r.GetOrdinal("kind")),
                Status = r.GetString(r.GetOrdinal("status"))
            });
        }
        return list;
    }
}
