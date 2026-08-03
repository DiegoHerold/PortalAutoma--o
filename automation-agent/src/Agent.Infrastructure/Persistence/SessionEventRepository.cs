using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Models.Sessions;
using Biason.AutomationAgent.Infrastructure.Database;

namespace Biason.AutomationAgent.Infrastructure.Persistence;

public sealed class SessionEventRepository : ISessionEventRepository
{
    private readonly SqliteDatabaseManager _db;

    public SessionEventRepository(SqliteDatabaseManager db) => _db = db;

    public async Task AddAsync(SessionEventRecord sessionEvent, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            INSERT INTO session_events (session_id, session_runner_instance_id, event_type, detail_json, occurred_at_utc)
            VALUES ($sid, $iid, $type, $detail, $at);
            """;
        cmd.Parameters.AddWithValue("$sid", sessionEvent.SessionId.HasValue ? sessionEvent.SessionId.Value : DBNull.Value);
        cmd.Parameters.AddWithValue("$iid", (object?)sessionEvent.SessionRunnerInstanceId ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$type", sessionEvent.EventType);
        cmd.Parameters.AddWithValue("$detail", (object?)sessionEvent.DetailJson ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$at", sessionEvent.OccurredAtUtc.ToString("o"));
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task<IReadOnlyList<SessionEventRecord>> GetRecentAsync(int count, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT * FROM session_events ORDER BY occurred_at_utc DESC LIMIT $count;";
        cmd.Parameters.AddWithValue("$count", count);
        var list = new List<SessionEventRecord>();
        using var reader = await cmd.ExecuteReaderAsync(ct);
        while (await reader.ReadAsync(ct))
        {
            list.Add(new SessionEventRecord
            {
                Id = reader.GetInt64(reader.GetOrdinal("id")),
                SessionId = reader.IsDBNull(reader.GetOrdinal("session_id")) ? null : reader.GetInt32(reader.GetOrdinal("session_id")),
                SessionRunnerInstanceId = reader.IsDBNull(reader.GetOrdinal("session_runner_instance_id")) ? null : reader.GetString(reader.GetOrdinal("session_runner_instance_id")),
                EventType = reader.GetString(reader.GetOrdinal("event_type")),
                DetailJson = reader.IsDBNull(reader.GetOrdinal("detail_json")) ? null : reader.GetString(reader.GetOrdinal("detail_json")),
                OccurredAtUtc = DateTime.Parse(reader.GetString(reader.GetOrdinal("occurred_at_utc")))
            });
        }
        return list;
    }
}
