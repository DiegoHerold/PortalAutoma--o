using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Interactive;
using Biason.AutomationAgent.Infrastructure.Database;
using Microsoft.Data.Sqlite;

namespace Biason.AutomationAgent.Infrastructure.Persistence;

public sealed class DesktopLockRepository : IDesktopLockRepository
{
    private static readonly string[] BlockingStatuses = { "Reserved", "Committed", "Active" };
    private readonly SqliteDatabaseManager _db;

    public DesktopLockRepository(SqliteDatabaseManager db) => _db = db;

    public async Task<bool> TryAcquireAsync(IReadOnlyList<ResourceLockRecord> locks, DateTime nowUtc, CancellationToken ct = default)
    {
        if (locks.Count == 0) return true;

        using var conn = _db.CreateConnection();
        using var tx = conn.BeginTransaction();
        try
        {
            await MarkExpiredAsync(conn, tx, nowUtc, ct);

            foreach (var item in locks)
            {
                using var conflict = conn.CreateCommand();
                conflict.Transaction = tx;
                conflict.CommandText = """
                    SELECT owner_execution_attempt_id
                    FROM resource_locks
                    WHERE resource_key = $key
                      AND status IN ('Reserved','Committed','Active')
                      AND lease_expires_at_utc > $now
                      AND owner_execution_attempt_id <> $attempt
                    LIMIT 1;
                    """;
                conflict.Parameters.AddWithValue("$key", item.LockKey);
                conflict.Parameters.AddWithValue("$now", nowUtc.ToString("o"));
                conflict.Parameters.AddWithValue("$attempt", item.OwnerAttemptId);
                var existing = await conflict.ExecuteScalarAsync(ct);
                if (existing is not null)
                {
                    tx.Rollback();
                    return false;
                }
            }

            foreach (var item in locks)
            {
                using var cmd = conn.CreateCommand();
                cmd.Transaction = tx;
                cmd.CommandText = """
                    INSERT INTO resource_locks (
                        resource_key, owner_execution_id, owner_execution_attempt_id, session_id,
                        acquired_at_utc, lease_expires_at_utc, last_renewed_at_utc, released_at_utc, status)
                    VALUES ($key, $eid, $aid, $sid, $created, $expires, $renewed, NULL, $status)
                    ON CONFLICT(resource_key) DO UPDATE SET
                        owner_execution_id = excluded.owner_execution_id,
                        owner_execution_attempt_id = excluded.owner_execution_attempt_id,
                        session_id = excluded.session_id,
                        acquired_at_utc = excluded.acquired_at_utc,
                        lease_expires_at_utc = excluded.lease_expires_at_utc,
                        last_renewed_at_utc = excluded.last_renewed_at_utc,
                        released_at_utc = NULL,
                        status = excluded.status
                    WHERE resource_locks.status IN ('Stale','Released')
                       OR resource_locks.lease_expires_at_utc <= $now
                       OR resource_locks.owner_execution_attempt_id = $aid;
                    """;
                Bind(cmd, item);
                cmd.Parameters.AddWithValue("$now", nowUtc.ToString("o"));
                await cmd.ExecuteNonQueryAsync(ct);
            }

            tx.Commit();
            return true;
        }
        catch
        {
            tx.Rollback();
            throw;
        }
    }

    public async Task<IReadOnlyList<ResourceLockRecord>> GetAllAsync(CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT * FROM resource_locks ORDER BY resource_key;";
        return await ReadListAsync(cmd, ct);
    }

    public async Task<IReadOnlyList<ResourceLockRecord>> GetByOwnerAsync(string executionId, string attemptId, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            SELECT * FROM resource_locks
            WHERE owner_execution_id = $eid AND owner_execution_attempt_id = $aid
            ORDER BY resource_key;
            """;
        cmd.Parameters.AddWithValue("$eid", executionId);
        cmd.Parameters.AddWithValue("$aid", attemptId);
        return await ReadListAsync(cmd, ct);
    }

    public Task CommitAsync(string executionId, string attemptId, DateTime nowUtc, CancellationToken ct = default)
        => UpdateOwnerStatusAsync(executionId, attemptId, DesktopLockStatus.Committed, nowUtc, null, ct);

    public Task ActivateAsync(string executionId, string attemptId, DateTime nowUtc, CancellationToken ct = default)
        => UpdateOwnerStatusAsync(executionId, attemptId, DesktopLockStatus.Active, nowUtc, null, ct);

    public async Task RenewAsync(string executionId, string attemptId, DateTime nowUtc, DateTime leaseExpiresAtUtc, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            UPDATE resource_locks
            SET last_renewed_at_utc = $now, lease_expires_at_utc = $expires
            WHERE owner_execution_id = $eid
              AND owner_execution_attempt_id = $aid
              AND status IN ('Reserved','Committed','Active');
            """;
        cmd.Parameters.AddWithValue("$now", nowUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$expires", leaseExpiresAtUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$eid", executionId);
        cmd.Parameters.AddWithValue("$aid", attemptId);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task ReleaseAsync(string executionId, string attemptId, DateTime nowUtc, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            UPDATE resource_locks
            SET status = 'Released', released_at_utc = $now, last_renewed_at_utc = COALESCE(last_renewed_at_utc, $now)
            WHERE owner_execution_id = $eid
              AND owner_execution_attempt_id = $aid
              AND status <> 'Released';
            """;
        cmd.Parameters.AddWithValue("$now", nowUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$eid", executionId);
        cmd.Parameters.AddWithValue("$aid", attemptId);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task<int> MarkExpiredAsync(DateTime nowUtc, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var tx = conn.BeginTransaction();
        var count = await MarkExpiredAsync(conn, tx, nowUtc, ct);
        tx.Commit();
        return count;
    }

    private async Task UpdateOwnerStatusAsync(string executionId, string attemptId, DesktopLockStatus status, DateTime nowUtc, DateTime? leaseExpiresAtUtc, CancellationToken ct)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            UPDATE resource_locks
            SET status = $status,
                last_renewed_at_utc = $now,
                lease_expires_at_utc = COALESCE($expires, lease_expires_at_utc)
            WHERE owner_execution_id = $eid
              AND owner_execution_attempt_id = $aid
              AND status IN ('Reserved','Committed','Active');
            """;
        cmd.Parameters.AddWithValue("$status", status.ToString());
        cmd.Parameters.AddWithValue("$now", nowUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$expires", leaseExpiresAtUtc?.ToString("o") ?? (object)DBNull.Value);
        cmd.Parameters.AddWithValue("$eid", executionId);
        cmd.Parameters.AddWithValue("$aid", attemptId);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    private static async Task<int> MarkExpiredAsync(SqliteConnection conn, SqliteTransaction tx, DateTime nowUtc, CancellationToken ct)
    {
        using var cmd = conn.CreateCommand();
        cmd.Transaction = tx;
        cmd.CommandText = """
            UPDATE resource_locks
            SET status = 'Stale', released_at_utc = COALESCE(released_at_utc, $now)
            WHERE status IN ('Reserved','Committed','Active')
              AND lease_expires_at_utc <= $now;
            """;
        cmd.Parameters.AddWithValue("$now", nowUtc.ToString("o"));
        return await cmd.ExecuteNonQueryAsync(ct);
    }

    private static void Bind(SqliteCommand cmd, ResourceLockRecord item)
    {
        cmd.Parameters.AddWithValue("$key", item.LockKey);
        cmd.Parameters.AddWithValue("$eid", item.OwnerExecutionId);
        cmd.Parameters.AddWithValue("$aid", item.OwnerAttemptId);
        cmd.Parameters.AddWithValue("$sid", item.SessionId.HasValue ? item.SessionId.Value : DBNull.Value);
        cmd.Parameters.AddWithValue("$created", item.CreatedAtUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$expires", item.LeaseExpiresAtUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$renewed", item.LastRenewedAtUtc?.ToString("o") ?? (object)DBNull.Value);
        cmd.Parameters.AddWithValue("$status", item.Status.ToString());
    }

    private static async Task<IReadOnlyList<ResourceLockRecord>> ReadListAsync(SqliteCommand cmd, CancellationToken ct)
    {
        var list = new List<ResourceLockRecord>();
        using var reader = await cmd.ExecuteReaderAsync(ct);
        while (await reader.ReadAsync(ct))
            list.Add(Map(reader));
        return list;
    }

    private static ResourceLockRecord Map(SqliteDataReader r) => new()
    {
        LockKey = r.GetString(r.GetOrdinal("resource_key")),
        OwnerExecutionId = r.GetString(r.GetOrdinal("owner_execution_id")),
        OwnerAttemptId = r.GetString(r.GetOrdinal("owner_execution_attempt_id")),
        SessionId = r.IsDBNull(r.GetOrdinal("session_id")) ? null : r.GetInt32(r.GetOrdinal("session_id")),
        CreatedAtUtc = DateTime.Parse(r.GetString(r.GetOrdinal("acquired_at_utc"))),
        LeaseExpiresAtUtc = DateTime.Parse(r.GetString(r.GetOrdinal("lease_expires_at_utc"))),
        LastRenewedAtUtc = r.IsDBNull(r.GetOrdinal("last_renewed_at_utc")) ? null : DateTime.Parse(r.GetString(r.GetOrdinal("last_renewed_at_utc"))),
        ReleasedAtUtc = r.IsDBNull(r.GetOrdinal("released_at_utc")) ? null : DateTime.Parse(r.GetString(r.GetOrdinal("released_at_utc"))),
        Status = Enum.Parse<DesktopLockStatus>(r.GetString(r.GetOrdinal("status")), true)
    };
}
