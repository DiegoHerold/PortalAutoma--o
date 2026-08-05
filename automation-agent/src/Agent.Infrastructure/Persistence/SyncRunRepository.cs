using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Models.Execution;
using Biason.AutomationAgent.Infrastructure.Database;
using Microsoft.Data.Sqlite;

namespace Biason.AutomationAgent.Infrastructure.Persistence;

public sealed class SyncRunRepository : ISyncRunRepository
{
    private readonly SqliteDatabaseManager _db;

    public SyncRunRepository(SqliteDatabaseManager db) => _db = db;

    public async Task SaveAsync(SyncRunRecord run, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            INSERT INTO sync_runs (
                sync_id, connection_id, started_at_utc, completed_at_utc,
                running_executions_reported, leases_reported, outbox_pending_reported,
                reconciled_count, status, error_message
            ) VALUES (
                $id, $conn, $started, $completed, $running, $leases, $outbox, $reconciled, $status, $error
            );
            """;
        BindAll(cmd, run);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task CompleteAsync(SyncRunRecord run, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            UPDATE sync_runs SET
                completed_at_utc = $completed,
                running_executions_reported = $running,
                leases_reported = $leases,
                outbox_pending_reported = $outbox,
                reconciled_count = $reconciled,
                status = $status,
                error_message = $error
            WHERE sync_id = $id;
            """;
        BindAll(cmd, run);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task<SyncRunRecord?> GetLatestAsync(CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT * FROM sync_runs ORDER BY started_at_utc DESC LIMIT 1;";
        using var r = await cmd.ExecuteReaderAsync(ct);
        return await r.ReadAsync(ct) ? Map(r) : null;
    }

    private static void BindAll(SqliteCommand cmd, SyncRunRecord run)
    {
        cmd.Parameters.AddWithValue("$id", run.SyncId);
        cmd.Parameters.AddWithValue("$conn", (object?)run.ConnectionId ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$started", run.StartedAtUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$completed", run.CompletedAtUtc?.ToString("o") ?? (object)DBNull.Value);
        cmd.Parameters.AddWithValue("$running", run.RunningExecutionsReported);
        cmd.Parameters.AddWithValue("$leases", run.LeasesReported);
        cmd.Parameters.AddWithValue("$outbox", run.OutboxPendingReported);
        cmd.Parameters.AddWithValue("$reconciled", run.ReconciledCount);
        cmd.Parameters.AddWithValue("$status", run.Status);
        cmd.Parameters.AddWithValue("$error", (object?)run.ErrorMessage ?? DBNull.Value);
    }

    private static SyncRunRecord Map(SqliteDataReader r) => new()
    {
        SyncId = r.GetString(r.GetOrdinal("sync_id")),
        ConnectionId = r.IsDBNull(r.GetOrdinal("connection_id")) ? null : r.GetString(r.GetOrdinal("connection_id")),
        StartedAtUtc = DateTime.Parse(r.GetString(r.GetOrdinal("started_at_utc"))),
        CompletedAtUtc = r.IsDBNull(r.GetOrdinal("completed_at_utc")) ? null : DateTime.Parse(r.GetString(r.GetOrdinal("completed_at_utc"))),
        RunningExecutionsReported = r.GetInt32(r.GetOrdinal("running_executions_reported")),
        LeasesReported = r.GetInt32(r.GetOrdinal("leases_reported")),
        OutboxPendingReported = r.GetInt32(r.GetOrdinal("outbox_pending_reported")),
        ReconciledCount = r.GetInt32(r.GetOrdinal("reconciled_count")),
        Status = r.GetString(r.GetOrdinal("status")),
        ErrorMessage = r.IsDBNull(r.GetOrdinal("error_message")) ? null : r.GetString(r.GetOrdinal("error_message"))
    };
}
