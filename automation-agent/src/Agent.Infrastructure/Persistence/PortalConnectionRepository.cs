using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Connections;
using Biason.AutomationAgent.Infrastructure.Database;

namespace Biason.AutomationAgent.Infrastructure.Persistence;

/// <summary>
/// Persiste o estado da conexão com o Portal em <c>portal_connections</c> (upsert por
/// <c>connection_id</c>) e o histórico de transições em <c>connection_events</c>
/// (append-only). Tabelas criadas na Migration 3 — nenhuma migração nova aqui.
/// </summary>
public sealed class PortalConnectionRepository : IConnectionStateRepository
{
    private readonly SqliteDatabaseManager _db;
    private readonly IAgentIdentityService _identity;

    public PortalConnectionRepository(SqliteDatabaseManager db, IAgentIdentityService identity)
    {
        _db = db;
        _identity = identity;
    }

    public async Task SaveStatusAsync(ConnectionStatus status, CancellationToken ct = default)
    {
        // GetCachedIdentity é síncrono e não bate no banco de novo — a identidade já foi
        // carregada muito antes de qualquer conexão WebSocket ser tentada.
        var agentInstanceId = _identity.GetCachedIdentity()?.InstanceId ?? "unknown";

        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            INSERT INTO portal_connections
                (connection_id, agent_instance_id, state, endpoint, connected_at_utc,
                 disconnected_at_utc, last_message_at_utc, last_pong_at_utc,
                 disconnect_reason, reconnect_attempt)
            VALUES
                ($cid, $aiid, $state, $endpoint, $cat, $dat, $lmat, $lpat, $reason, $attempt)
            ON CONFLICT(connection_id) DO UPDATE SET
                agent_instance_id = excluded.agent_instance_id,
                state = excluded.state,
                endpoint = excluded.endpoint,
                connected_at_utc = excluded.connected_at_utc,
                disconnected_at_utc = excluded.disconnected_at_utc,
                last_message_at_utc = excluded.last_message_at_utc,
                last_pong_at_utc = excluded.last_pong_at_utc,
                disconnect_reason = excluded.disconnect_reason,
                reconnect_attempt = excluded.reconnect_attempt;
            """;
        cmd.Parameters.AddWithValue("$cid", status.ConnectionId);
        cmd.Parameters.AddWithValue("$aiid", agentInstanceId);
        cmd.Parameters.AddWithValue("$state", status.State.ToString());
        cmd.Parameters.AddWithValue("$endpoint", status.Endpoint);
        cmd.Parameters.AddWithValue("$cat", (object?)status.ConnectedAtUtc?.ToString("o") ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$dat", (object?)status.DisconnectedAtUtc?.ToString("o") ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$lmat", (object?)status.LastMessageAtUtc?.ToString("o") ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$lpat", (object?)status.LastPongAtUtc?.ToString("o") ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$reason", (object?)status.DisconnectReason ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$attempt", status.ReconnectAttempt);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task<ConnectionStatus?> GetLatestStatusAsync(CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            SELECT connection_id, state, endpoint, connected_at_utc, disconnected_at_utc,
                   last_message_at_utc, last_pong_at_utc, disconnect_reason, reconnect_attempt
            FROM portal_connections
            ORDER BY rowid DESC
            LIMIT 1;
            """;

        using var reader = await cmd.ExecuteReaderAsync(ct);
        if (!await reader.ReadAsync(ct))
            return null;

        return new ConnectionStatus
        {
            ConnectionId = reader.GetString(0),
            State = Enum.Parse<ConnectionState>(reader.GetString(1)),
            Endpoint = reader.GetString(2),
            ConnectedAtUtc = reader.IsDBNull(3) ? null : DateTime.Parse(reader.GetString(3)),
            DisconnectedAtUtc = reader.IsDBNull(4) ? null : DateTime.Parse(reader.GetString(4)),
            LastMessageAtUtc = reader.IsDBNull(5) ? null : DateTime.Parse(reader.GetString(5)),
            LastPongAtUtc = reader.IsDBNull(6) ? null : DateTime.Parse(reader.GetString(6)),
            DisconnectReason = reader.IsDBNull(7) ? null : reader.GetString(7),
            ReconnectAttempt = reader.GetInt32(8)
        };
    }

    public async Task RecordEventAsync(ConnectionEvent evt, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            INSERT INTO connection_events (connection_id, from_state, to_state, reason, detail, occurred_at_utc)
            VALUES ($cid, $from, $to, $reason, $detail, $occurred);
            """;
        cmd.Parameters.AddWithValue("$cid", (object?)evt.ConnectionId ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$from", (object?)evt.FromState?.ToString() ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$to", evt.ToState.ToString());
        cmd.Parameters.AddWithValue("$reason", (object?)evt.Reason ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$detail", (object?)evt.Detail ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$occurred", evt.OccurredAtUtc.ToString("o"));
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task<IReadOnlyList<ConnectionEvent>> GetRecentEventsAsync(int limit = 50, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            SELECT connection_id, from_state, to_state, reason, detail, occurred_at_utc
            FROM connection_events
            ORDER BY occurred_at_utc DESC, id DESC
            LIMIT $limit;
            """;
        cmd.Parameters.AddWithValue("$limit", limit);

        var results = new List<ConnectionEvent>();
        using var reader = await cmd.ExecuteReaderAsync(ct);
        while (await reader.ReadAsync(ct))
        {
            results.Add(new ConnectionEvent
            {
                ConnectionId = reader.IsDBNull(0) ? null : reader.GetString(0),
                FromState = reader.IsDBNull(1) ? null : Enum.Parse<ConnectionState>(reader.GetString(1)),
                ToState = Enum.Parse<ConnectionState>(reader.GetString(2)),
                Reason = reader.IsDBNull(3) ? null : reader.GetString(3),
                Detail = reader.IsDBNull(4) ? null : reader.GetString(4),
                OccurredAtUtc = DateTime.Parse(reader.GetString(5))
            });
        }
        return results;
    }
}
