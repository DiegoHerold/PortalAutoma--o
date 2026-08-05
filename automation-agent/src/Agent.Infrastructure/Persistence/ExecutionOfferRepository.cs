using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Models.Execution;
using Biason.AutomationAgent.Infrastructure.Database;
using Microsoft.Data.Sqlite;

namespace Biason.AutomationAgent.Infrastructure.Persistence;

public sealed class ExecutionOfferRepository : IExecutionOfferRepository
{
    private readonly SqliteDatabaseManager _db;
    public ExecutionOfferRepository(SqliteDatabaseManager db) => _db = db;

    public async Task SaveAsync(ExecutionOfferRecord offer, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            INSERT INTO execution_offers (
                offer_message_id, execution_id, execution_attempt_id, automation_id, automation_version,
                runtime_id, runtime_version, mode, pool, offer_payload_json, decision, reason_code,
                reason_message, reservation_id, received_at_utc, decided_at_utc, reservation_expires_at_utc
            ) VALUES (
                $id, $eid, $aid, $autoid, $autover, $rid, $rver, $mode, $pool, $payload, $decision,
                $rcode, $rmsg, $resid, $recv, $dec, $resexp
            );
            """;
        cmd.Parameters.AddWithValue("$id", offer.OfferMessageId);
        cmd.Parameters.AddWithValue("$eid", offer.ExecutionId);
        cmd.Parameters.AddWithValue("$aid", offer.ExecutionAttemptId);
        cmd.Parameters.AddWithValue("$autoid", offer.AutomationId);
        cmd.Parameters.AddWithValue("$autover", (object?)offer.AutomationVersion ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$rid", (object?)offer.RuntimeId ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$rver", (object?)offer.RuntimeVersion ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$mode", offer.Mode);
        cmd.Parameters.AddWithValue("$pool", offer.Pool);
        cmd.Parameters.AddWithValue("$payload", offer.OfferPayloadJson);
        cmd.Parameters.AddWithValue("$decision", offer.Decision);
        cmd.Parameters.AddWithValue("$rcode", (object?)offer.ReasonCode ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$rmsg", (object?)offer.ReasonMessage ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$resid", (object?)offer.ReservationId ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$recv", offer.ReceivedAtUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$dec", offer.DecidedAtUtc?.ToString("o") ?? (object)DBNull.Value);
        cmd.Parameters.AddWithValue("$resexp", offer.ReservationExpiresAtUtc?.ToString("o") ?? (object)DBNull.Value);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task<ExecutionOfferRecord?> GetByMessageIdAsync(string offerMessageId, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT * FROM execution_offers WHERE offer_message_id = $id;";
        cmd.Parameters.AddWithValue("$id", offerMessageId);
        using var r = await cmd.ExecuteReaderAsync(ct);
        return await r.ReadAsync(ct) ? Map(r) : null;
    }

    public async Task<ExecutionOfferRecord?> GetLatestByAttemptAsync(string executionAttemptId, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            SELECT * FROM execution_offers
            WHERE execution_attempt_id = $aid
            ORDER BY received_at_utc DESC
            LIMIT 1;
            """;
        cmd.Parameters.AddWithValue("$aid", executionAttemptId);
        using var r = await cmd.ExecuteReaderAsync(ct);
        return await r.ReadAsync(ct) ? Map(r) : null;
    }

    public async Task<IReadOnlyList<ExecutionOfferRecord>> GetRecentAsync(int limit = 100, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            SELECT * FROM execution_offers
            ORDER BY received_at_utc DESC
            LIMIT $limit;
            """;
        cmd.Parameters.AddWithValue("$limit", limit);
        var list = new List<ExecutionOfferRecord>();
        using var r = await cmd.ExecuteReaderAsync(ct);
        while (await r.ReadAsync(ct))
            list.Add(Map(r));
        return list;
    }

    private static ExecutionOfferRecord Map(SqliteDataReader r) => new()
    {
        OfferMessageId = r.GetString(r.GetOrdinal("offer_message_id")),
        ExecutionId = r.GetString(r.GetOrdinal("execution_id")),
        ExecutionAttemptId = r.GetString(r.GetOrdinal("execution_attempt_id")),
        AutomationId = r.GetString(r.GetOrdinal("automation_id")),
        AutomationVersion = r.IsDBNull(r.GetOrdinal("automation_version")) ? null : r.GetString(r.GetOrdinal("automation_version")),
        RuntimeId = r.IsDBNull(r.GetOrdinal("runtime_id")) ? null : r.GetString(r.GetOrdinal("runtime_id")),
        RuntimeVersion = r.IsDBNull(r.GetOrdinal("runtime_version")) ? null : r.GetString(r.GetOrdinal("runtime_version")),
        Mode = r.GetString(r.GetOrdinal("mode")),
        Pool = r.GetString(r.GetOrdinal("pool")),
        OfferPayloadJson = r.GetString(r.GetOrdinal("offer_payload_json")),
        Decision = r.GetString(r.GetOrdinal("decision")),
        ReasonCode = r.IsDBNull(r.GetOrdinal("reason_code")) ? null : r.GetString(r.GetOrdinal("reason_code")),
        ReasonMessage = r.IsDBNull(r.GetOrdinal("reason_message")) ? null : r.GetString(r.GetOrdinal("reason_message")),
        ReservationId = r.IsDBNull(r.GetOrdinal("reservation_id")) ? null : r.GetString(r.GetOrdinal("reservation_id")),
        ReceivedAtUtc = DateTime.Parse(r.GetString(r.GetOrdinal("received_at_utc"))),
        DecidedAtUtc = r.IsDBNull(r.GetOrdinal("decided_at_utc")) ? null : DateTime.Parse(r.GetString(r.GetOrdinal("decided_at_utc"))),
        ReservationExpiresAtUtc = r.IsDBNull(r.GetOrdinal("reservation_expires_at_utc")) ? null : DateTime.Parse(r.GetString(r.GetOrdinal("reservation_expires_at_utc")))
    };
}
