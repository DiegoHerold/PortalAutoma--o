using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Models.Sessions;
using Biason.AutomationAgent.Infrastructure.Database;

namespace Biason.AutomationAgent.Infrastructure.Persistence;

public sealed class SessionRunnerConnectionRepository : ISessionRunnerConnectionRepository
{
    private readonly SqliteDatabaseManager _db;

    public SessionRunnerConnectionRepository(SqliteDatabaseManager db) => _db = db;

    public async Task<long> AddAsync(SessionRunnerConnectionRecord connection, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            INSERT INTO session_runner_connections (
                session_runner_instance_id, session_id, connected_at_utc, authenticated_at_utc,
                disconnected_at_utc, disconnect_reason, remote_process_id, protocol_version, status)
            VALUES ($iid, $sid, $cat, $aat, $dat, $reason, $pid, $version, $status);
            SELECT last_insert_rowid();
            """;
        cmd.Parameters.AddWithValue("$iid", connection.SessionRunnerInstanceId);
        cmd.Parameters.AddWithValue("$sid", connection.SessionId);
        cmd.Parameters.AddWithValue("$cat", connection.ConnectedAtUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$aat", connection.AuthenticatedAtUtc?.ToString("o") ?? (object)DBNull.Value);
        cmd.Parameters.AddWithValue("$dat", connection.DisconnectedAtUtc?.ToString("o") ?? (object)DBNull.Value);
        cmd.Parameters.AddWithValue("$reason", (object?)connection.DisconnectReason ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$pid", connection.RemoteProcessId.HasValue ? connection.RemoteProcessId.Value : DBNull.Value);
        cmd.Parameters.AddWithValue("$version", (object?)connection.ProtocolVersion ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$status", connection.Status);
        var result = await cmd.ExecuteScalarAsync(ct);
        return Convert.ToInt64(result);
    }

    public async Task MarkAuthenticatedAsync(long id, DateTime authenticatedAtUtc, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "UPDATE session_runner_connections SET authenticated_at_utc = $at, status = 'authenticated' WHERE id = $id;";
        cmd.Parameters.AddWithValue("$at", authenticatedAtUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$id", id);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task MarkDisconnectedAsync(long id, DateTime disconnectedAtUtc, string reason, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "UPDATE session_runner_connections SET disconnected_at_utc = $at, disconnect_reason = $reason, status = 'disconnected' WHERE id = $id;";
        cmd.Parameters.AddWithValue("$at", disconnectedAtUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$reason", reason);
        cmd.Parameters.AddWithValue("$id", id);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task<IReadOnlyList<SessionRunnerConnectionRecord>> GetRecentAsync(int count, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT * FROM session_runner_connections ORDER BY connected_at_utc DESC LIMIT $count;";
        cmd.Parameters.AddWithValue("$count", count);
        var list = new List<SessionRunnerConnectionRecord>();
        using var reader = await cmd.ExecuteReaderAsync(ct);
        while (await reader.ReadAsync(ct))
        {
            list.Add(new SessionRunnerConnectionRecord
            {
                Id = reader.GetInt64(reader.GetOrdinal("id")),
                SessionRunnerInstanceId = reader.GetString(reader.GetOrdinal("session_runner_instance_id")),
                SessionId = reader.GetInt32(reader.GetOrdinal("session_id")),
                ConnectedAtUtc = DateTime.Parse(reader.GetString(reader.GetOrdinal("connected_at_utc"))),
                AuthenticatedAtUtc = reader.IsDBNull(reader.GetOrdinal("authenticated_at_utc")) ? null : DateTime.Parse(reader.GetString(reader.GetOrdinal("authenticated_at_utc"))),
                DisconnectedAtUtc = reader.IsDBNull(reader.GetOrdinal("disconnected_at_utc")) ? null : DateTime.Parse(reader.GetString(reader.GetOrdinal("disconnected_at_utc"))),
                DisconnectReason = reader.IsDBNull(reader.GetOrdinal("disconnect_reason")) ? null : reader.GetString(reader.GetOrdinal("disconnect_reason")),
                RemoteProcessId = reader.IsDBNull(reader.GetOrdinal("remote_process_id")) ? null : reader.GetInt32(reader.GetOrdinal("remote_process_id")),
                ProtocolVersion = reader.IsDBNull(reader.GetOrdinal("protocol_version")) ? null : reader.GetString(reader.GetOrdinal("protocol_version")),
                Status = reader.GetString(reader.GetOrdinal("status"))
            });
        }
        return list;
    }
}
