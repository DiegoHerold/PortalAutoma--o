using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Capacity;
using Biason.AutomationAgent.Infrastructure.Database;

namespace Biason.AutomationAgent.Infrastructure.Persistence;

public sealed class ReservationRepository : IReservationRepository
{
    private readonly SqliteDatabaseManager _db;
    public ReservationRepository(SqliteDatabaseManager db) => _db = db;

    public async Task SaveAsync(ResourceReservation reservation, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            INSERT INTO resource_reservations (reservation_id, execution_id, pool, slots, status, created_at_utc, expires_at_utc, released_at_utc)
            VALUES ($rid, $eid, $p, $s, $st, $c, $e, $r);
            """;
        cmd.Parameters.AddWithValue("$rid", reservation.ReservationId);
        cmd.Parameters.AddWithValue("$eid", reservation.ExecutionId);
        cmd.Parameters.AddWithValue("$p", reservation.Pool.ToString());
        cmd.Parameters.AddWithValue("$s", reservation.Slots);
        cmd.Parameters.AddWithValue("$st", reservation.Status.ToString());
        cmd.Parameters.AddWithValue("$c", reservation.CreatedAtUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$e", reservation.ExpiresAtUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$r", reservation.ReleasedAtUtc?.ToString("o") ?? (object)DBNull.Value);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task<ResourceReservation?> GetAsync(string reservationId, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT * FROM resource_reservations WHERE reservation_id = $rid;";
        cmd.Parameters.AddWithValue("$rid", reservationId);
        using var r = await cmd.ExecuteReaderAsync(ct);
        if (!await r.ReadAsync(ct)) return null;
        return Map(r);
    }

    // "Ativa" = ainda consome capacidade: Temporary (aguardando commit) ou
    // Committed (execução em preparo/andamento). Só Released/Expired/Cancelled
    // saem da contagem.
    public async Task<IReadOnlyList<ResourceReservation>> GetActiveAsync(CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT * FROM resource_reservations WHERE status IN ('Temporary','Committed') ORDER BY created_at_utc;";
        return await ReadListAsync(cmd, ct);
    }

    // Só reservas Temporary expiram por TTL — Committed não tem expiração
    // (seção 8: "Committed não tem expiração automática por tempo").
    public async Task<IReadOnlyList<ResourceReservation>> GetExpiredAsync(DateTime now, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT * FROM resource_reservations WHERE status = 'Temporary' AND expires_at_utc < $now;";
        cmd.Parameters.AddWithValue("$now", now.ToString("o"));
        return await ReadListAsync(cmd, ct);
    }

    public async Task UpdateStatusAsync(string reservationId, ReservationStatus status, DateTime? releasedAt, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "UPDATE resource_reservations SET status = $st, released_at_utc = $r WHERE reservation_id = $rid;";
        cmd.Parameters.AddWithValue("$st", status.ToString());
        cmd.Parameters.AddWithValue("$r", releasedAt?.ToString("o") ?? (object)DBNull.Value);
        cmd.Parameters.AddWithValue("$rid", reservationId);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task<int> CountActiveByPoolAsync(PoolType pool, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT COALESCE(SUM(slots),0) FROM resource_reservations WHERE pool = $p AND status IN ('Temporary','Committed');";
        cmd.Parameters.AddWithValue("$p", pool.ToString());
        var result = await cmd.ExecuteScalarAsync(ct);
        return Convert.ToInt32(result);
    }

    // Compare-and-set: só transiciona se ainda estiver Temporary e não vencida.
    // Uma única instrução UPDATE — o SQLite serializa escritores no nível do
    // arquivo/conexão, então o resultado de ExecuteNonQueryAsync (linhas
    // afetadas) é uma checagem atômica confiável contra a race com expiração
    // (Bloco 5.5, seção 15).
    public async Task<bool> TryCommitAsync(string reservationId, DateTime nowUtc, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            UPDATE resource_reservations
            SET status = 'Committed'
            WHERE reservation_id = $rid AND status = 'Temporary' AND expires_at_utc > $now;
            """;
        cmd.Parameters.AddWithValue("$rid", reservationId);
        cmd.Parameters.AddWithValue("$now", nowUtc.ToString("o"));
        var affected = await cmd.ExecuteNonQueryAsync(ct);
        return affected > 0;
    }

    public async Task<bool> TryExpireAsync(string reservationId, DateTime nowUtc, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            UPDATE resource_reservations
            SET status = 'Expired', released_at_utc = $now
            WHERE reservation_id = $rid AND status = 'Temporary' AND expires_at_utc <= $now;
            """;
        cmd.Parameters.AddWithValue("$rid", reservationId);
        cmd.Parameters.AddWithValue("$now", nowUtc.ToString("o"));
        var affected = await cmd.ExecuteNonQueryAsync(ct);
        return affected > 0;
    }

    private static async Task<IReadOnlyList<ResourceReservation>> ReadListAsync(Microsoft.Data.Sqlite.SqliteCommand cmd, CancellationToken ct)
    {
        var list = new List<ResourceReservation>();
        using var r = await cmd.ExecuteReaderAsync(ct);
        while (await r.ReadAsync(ct)) list.Add(Map(r));
        return list;
    }

    private static ResourceReservation Map(Microsoft.Data.Sqlite.SqliteDataReader r) => new()
    {
        ReservationId = r.GetString(r.GetOrdinal("reservation_id")),
        ExecutionId = r.GetString(r.GetOrdinal("execution_id")),
        Pool = Enum.Parse<PoolType>(r.GetString(r.GetOrdinal("pool")), true),
        Slots = r.GetInt32(r.GetOrdinal("slots")),
        Status = Enum.Parse<ReservationStatus>(r.GetString(r.GetOrdinal("status")), true),
        CreatedAtUtc = DateTime.Parse(r.GetString(r.GetOrdinal("created_at_utc"))),
        ExpiresAtUtc = DateTime.Parse(r.GetString(r.GetOrdinal("expires_at_utc"))),
        ReleasedAtUtc = r.IsDBNull(r.GetOrdinal("released_at_utc")) ? null : DateTime.Parse(r.GetString(r.GetOrdinal("released_at_utc")))
    };
}
