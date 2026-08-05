using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Models.Execution;
using Biason.AutomationAgent.Infrastructure.Database;
using Microsoft.Data.Sqlite;

namespace Biason.AutomationAgent.Infrastructure.Persistence;

public sealed class ExecutionLeaseRepository : IExecutionLeaseRepository
{
    private readonly SqliteDatabaseManager _db;
    public ExecutionLeaseRepository(SqliteDatabaseManager db) => _db = db;

    public async Task SaveAsync(ExecutionLeaseRecord lease, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            INSERT INTO execution_leases (
                lease_id, execution_id, execution_attempt_id, state, granted_at_utc,
                expires_at_utc, last_renewed_at_utc, renew_attempt_count, lost_at_utc, lost_reason
            ) VALUES ($id, $eid, $aid, $state, $granted, $expires, $renewed, $attempts, $lostAt, $lostReason);
            """;
        BindAll(cmd, lease);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task UpdateAsync(ExecutionLeaseRecord lease, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            UPDATE execution_leases SET
                state = $state, expires_at_utc = $expires, last_renewed_at_utc = $renewed,
                renew_attempt_count = $attempts, lost_at_utc = $lostAt, lost_reason = $lostReason
            WHERE lease_id = $id;
            """;
        BindAll(cmd, lease);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task<ExecutionLeaseRecord?> GetAsync(string leaseId, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT * FROM execution_leases WHERE lease_id = $id;";
        cmd.Parameters.AddWithValue("$id", leaseId);
        using var r = await cmd.ExecuteReaderAsync(ct);
        return await r.ReadAsync(ct) ? Map(r) : null;
    }

    public async Task<ExecutionLeaseRecord?> GetByAttemptAsync(string executionAttemptId, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT * FROM execution_leases WHERE execution_attempt_id = $aid ORDER BY granted_at_utc DESC LIMIT 1;";
        cmd.Parameters.AddWithValue("$aid", executionAttemptId);
        using var r = await cmd.ExecuteReaderAsync(ct);
        return await r.ReadAsync(ct) ? Map(r) : null;
    }

    public async Task<IReadOnlyList<ExecutionLeaseRecord>> GetNonFinalAsync(CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT * FROM execution_leases WHERE state IN ('active','at_risk');";
        var list = new List<ExecutionLeaseRecord>();
        using var r = await cmd.ExecuteReaderAsync(ct);
        while (await r.ReadAsync(ct)) list.Add(Map(r));
        return list;
    }

    private static void BindAll(SqliteCommand cmd, ExecutionLeaseRecord lease)
    {
        cmd.Parameters.AddWithValue("$id", lease.LeaseId);
        cmd.Parameters.AddWithValue("$eid", lease.ExecutionId);
        cmd.Parameters.AddWithValue("$aid", lease.ExecutionAttemptId);
        cmd.Parameters.AddWithValue("$state", lease.State);
        cmd.Parameters.AddWithValue("$granted", lease.GrantedAtUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$expires", lease.ExpiresAtUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$renewed", lease.LastRenewedAtUtc?.ToString("o") ?? (object)DBNull.Value);
        cmd.Parameters.AddWithValue("$attempts", lease.RenewAttemptCount);
        cmd.Parameters.AddWithValue("$lostAt", lease.LostAtUtc?.ToString("o") ?? (object)DBNull.Value);
        cmd.Parameters.AddWithValue("$lostReason", (object?)lease.LostReason ?? DBNull.Value);
    }

    private static ExecutionLeaseRecord Map(SqliteDataReader r) => new()
    {
        LeaseId = r.GetString(r.GetOrdinal("lease_id")),
        ExecutionId = r.GetString(r.GetOrdinal("execution_id")),
        ExecutionAttemptId = r.GetString(r.GetOrdinal("execution_attempt_id")),
        State = r.GetString(r.GetOrdinal("state")),
        GrantedAtUtc = DateTime.Parse(r.GetString(r.GetOrdinal("granted_at_utc"))),
        ExpiresAtUtc = DateTime.Parse(r.GetString(r.GetOrdinal("expires_at_utc"))),
        LastRenewedAtUtc = r.IsDBNull(r.GetOrdinal("last_renewed_at_utc")) ? null : DateTime.Parse(r.GetString(r.GetOrdinal("last_renewed_at_utc"))),
        RenewAttemptCount = r.GetInt32(r.GetOrdinal("renew_attempt_count")),
        LostAtUtc = r.IsDBNull(r.GetOrdinal("lost_at_utc")) ? null : DateTime.Parse(r.GetString(r.GetOrdinal("lost_at_utc"))),
        LostReason = r.IsDBNull(r.GetOrdinal("lost_reason")) ? null : r.GetString(r.GetOrdinal("lost_reason"))
    };
}
