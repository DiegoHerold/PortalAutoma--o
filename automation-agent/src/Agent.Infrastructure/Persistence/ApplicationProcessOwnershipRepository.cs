using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Models.Interactive;
using Biason.AutomationAgent.Infrastructure.Database;
using Microsoft.Data.Sqlite;

namespace Biason.AutomationAgent.Infrastructure.Persistence;

public sealed class ApplicationProcessOwnershipRepository : IApplicationProcessOwnershipRepository
{
    private readonly SqliteDatabaseManager _db;
    public ApplicationProcessOwnershipRepository(SqliteDatabaseManager db) => _db = db;

    public async Task AddAsync(ApplicationProcessOwnershipRecord ownership, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            INSERT INTO application_process_ownership (
                execution_id, execution_attempt_id, application_key, process_id, session_id,
                process_path, window_title, started_at_utc, observed_at_utc,
                ownership_kind, policy, status)
            VALUES ($eid, $aid, $app, $pid, $sid, $path, $title, $started, $observed, $kind, $policy, $status);
            """;
        cmd.Parameters.AddWithValue("$eid", ownership.ExecutionId);
        cmd.Parameters.AddWithValue("$aid", ownership.AttemptId);
        cmd.Parameters.AddWithValue("$app", ownership.ApplicationKey);
        cmd.Parameters.AddWithValue("$pid", ownership.ProcessId);
        cmd.Parameters.AddWithValue("$sid", ownership.SessionId.HasValue ? ownership.SessionId.Value : DBNull.Value);
        cmd.Parameters.AddWithValue("$path", (object?)ownership.ProcessPath ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$title", (object?)ownership.WindowTitle ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$started", ownership.StartedAtUtc?.ToString("o") ?? (object)DBNull.Value);
        cmd.Parameters.AddWithValue("$observed", ownership.ObservedAtUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$kind", ownership.OwnershipKind);
        cmd.Parameters.AddWithValue("$policy", ownership.Policy);
        cmd.Parameters.AddWithValue("$status", ownership.Status);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task<IReadOnlyList<ApplicationProcessOwnershipRecord>> GetAllAsync(CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT * FROM application_process_ownership ORDER BY observed_at_utc DESC;";
        return await ReadListAsync(cmd, ct);
    }

    public async Task<IReadOnlyList<ApplicationProcessOwnershipRecord>> GetByAttemptAsync(string executionId, string attemptId, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT * FROM application_process_ownership WHERE execution_id = $eid AND execution_attempt_id = $aid ORDER BY observed_at_utc;";
        cmd.Parameters.AddWithValue("$eid", executionId);
        cmd.Parameters.AddWithValue("$aid", attemptId);
        return await ReadListAsync(cmd, ct);
    }

    private static async Task<IReadOnlyList<ApplicationProcessOwnershipRecord>> ReadListAsync(SqliteCommand cmd, CancellationToken ct)
    {
        var list = new List<ApplicationProcessOwnershipRecord>();
        using var r = await cmd.ExecuteReaderAsync(ct);
        while (await r.ReadAsync(ct))
        {
            list.Add(new ApplicationProcessOwnershipRecord
            {
                Id = r.GetInt64(r.GetOrdinal("id")),
                ExecutionId = r.GetString(r.GetOrdinal("execution_id")),
                AttemptId = r.GetString(r.GetOrdinal("execution_attempt_id")),
                ApplicationKey = r.GetString(r.GetOrdinal("application_key")),
                ProcessId = r.GetInt32(r.GetOrdinal("process_id")),
                SessionId = r.IsDBNull(r.GetOrdinal("session_id")) ? null : r.GetInt32(r.GetOrdinal("session_id")),
                ProcessPath = r.IsDBNull(r.GetOrdinal("process_path")) ? null : r.GetString(r.GetOrdinal("process_path")),
                WindowTitle = r.IsDBNull(r.GetOrdinal("window_title")) ? null : r.GetString(r.GetOrdinal("window_title")),
                StartedAtUtc = r.IsDBNull(r.GetOrdinal("started_at_utc")) ? null : DateTime.Parse(r.GetString(r.GetOrdinal("started_at_utc"))),
                ObservedAtUtc = DateTime.Parse(r.GetString(r.GetOrdinal("observed_at_utc"))),
                OwnershipKind = r.GetString(r.GetOrdinal("ownership_kind")),
                Policy = r.GetString(r.GetOrdinal("policy")),
                Status = r.GetString(r.GetOrdinal("status"))
            });
        }
        return list;
    }
}
