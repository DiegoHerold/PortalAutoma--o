using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Sessions;
using Biason.AutomationAgent.Infrastructure.Database;
using Biason.AutomationAgent.Protocol.Serialization;

namespace Biason.AutomationAgent.Infrastructure.Persistence;

public sealed class SessionRunnerRepository : ISessionRunnerRepository
{
    private readonly SqliteDatabaseManager _db;

    public SessionRunnerRepository(SqliteDatabaseManager db) => _db = db;

    public async Task UpsertAsync(SessionRunnerRecord runner, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            INSERT INTO session_runners (
                session_runner_instance_id, session_id, user_name, session_type, process_id, version,
                desktop_state, capabilities_json, state, registered_at_utc, last_heartbeat_at_utc,
                disconnected_at_utc, session_token_fingerprint, session_token_expires_at_utc)
            VALUES ($iid, $sid, $user, $stype, $pid, $ver, $desktop, NULL, $state, $reg, $hb, $disc, $fp, $texp)
            ON CONFLICT(session_runner_instance_id) DO UPDATE SET
                session_id = excluded.session_id,
                user_name = excluded.user_name,
                session_type = excluded.session_type,
                process_id = excluded.process_id,
                version = excluded.version,
                desktop_state = excluded.desktop_state,
                state = excluded.state,
                last_heartbeat_at_utc = excluded.last_heartbeat_at_utc,
                disconnected_at_utc = excluded.disconnected_at_utc,
                session_token_fingerprint = excluded.session_token_fingerprint,
                session_token_expires_at_utc = excluded.session_token_expires_at_utc;
            """;
        Bind(cmd, runner);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task<SessionRunnerRecord?> GetAsync(string instanceId, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT * FROM session_runners WHERE session_runner_instance_id = $iid;";
        cmd.Parameters.AddWithValue("$iid", instanceId);
        using var reader = await cmd.ExecuteReaderAsync(ct);
        return await reader.ReadAsync(ct) ? Map(reader) : null;
    }

    public async Task<IReadOnlyList<SessionRunnerRecord>> GetAllAsync(CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT * FROM session_runners ORDER BY registered_at_utc DESC;";
        return await ReadListAsync(cmd, ct);
    }

    public async Task<IReadOnlyList<SessionRunnerRecord>> GetConnectedAsync(CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT * FROM session_runners WHERE state = 'Connected' ORDER BY registered_at_utc DESC;";
        return await ReadListAsync(cmd, ct);
    }

    public async Task UpdateHeartbeatAsync(string instanceId, DateTime heartbeatAtUtc, DesktopState desktop, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            UPDATE session_runners
            SET last_heartbeat_at_utc = $hb, desktop_state = $desktop, state = 'Connected'
            WHERE session_runner_instance_id = $iid;
            """;
        cmd.Parameters.AddWithValue("$hb", heartbeatAtUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$desktop", ProtocolJson.Serialize(desktop));
        cmd.Parameters.AddWithValue("$iid", instanceId);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task MarkDisconnectedAsync(string instanceId, DateTime disconnectedAtUtc, string reason, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            UPDATE session_runners
            SET state = 'Disconnected', disconnected_at_utc = $disc, session_token_fingerprint = NULL, session_token_expires_at_utc = NULL
            WHERE session_runner_instance_id = $iid;
            """;
        cmd.Parameters.AddWithValue("$disc", disconnectedAtUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$iid", instanceId);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task UpdateTokenFingerprintAsync(string instanceId, string fingerprint, DateTime expiresAtUtc, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            UPDATE session_runners
            SET session_token_fingerprint = $fp, session_token_expires_at_utc = $exp
            WHERE session_runner_instance_id = $iid;
            """;
        cmd.Parameters.AddWithValue("$fp", fingerprint);
        cmd.Parameters.AddWithValue("$exp", expiresAtUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$iid", instanceId);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task UpdateStateAsync(string instanceId, SessionRunnerConnectionState state, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "UPDATE session_runners SET state = $state WHERE session_runner_instance_id = $iid;";
        cmd.Parameters.AddWithValue("$state", state.ToString());
        cmd.Parameters.AddWithValue("$iid", instanceId);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    private static async Task<IReadOnlyList<SessionRunnerRecord>> ReadListAsync(Microsoft.Data.Sqlite.SqliteCommand cmd, CancellationToken ct)
    {
        var list = new List<SessionRunnerRecord>();
        using var reader = await cmd.ExecuteReaderAsync(ct);
        while (await reader.ReadAsync(ct)) list.Add(Map(reader));
        return list;
    }

    private static void Bind(Microsoft.Data.Sqlite.SqliteCommand cmd, SessionRunnerRecord r)
    {
        var user = string.IsNullOrWhiteSpace(r.DomainName) ? r.UserName : $"{r.DomainName}\\{r.UserName}";
        cmd.Parameters.AddWithValue("$iid", r.InstanceId);
        cmd.Parameters.AddWithValue("$sid", r.SessionId);
        cmd.Parameters.AddWithValue("$user", (object?)user ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$stype", r.SessionType.ToString());
        cmd.Parameters.AddWithValue("$pid", r.ProcessId.HasValue ? r.ProcessId.Value : DBNull.Value);
        cmd.Parameters.AddWithValue("$ver", (object?)r.Version ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$desktop", ProtocolJson.Serialize(r.Desktop));
        cmd.Parameters.AddWithValue("$state", r.State.ToString());
        cmd.Parameters.AddWithValue("$reg", r.RegisteredAtUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$hb", r.LastHeartbeatAtUtc?.ToString("o") ?? (object)DBNull.Value);
        cmd.Parameters.AddWithValue("$disc", r.DisconnectedAtUtc?.ToString("o") ?? (object)DBNull.Value);
        cmd.Parameters.AddWithValue("$fp", (object?)r.SessionTokenFingerprint ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$texp", r.SessionTokenExpiresAtUtc?.ToString("o") ?? (object)DBNull.Value);
    }

    private static SessionRunnerRecord Map(Microsoft.Data.Sqlite.SqliteDataReader reader)
    {
        var desktopJson = reader.IsDBNull(reader.GetOrdinal("desktop_state"))
            ? null
            : reader.GetString(reader.GetOrdinal("desktop_state"));

        return new SessionRunnerRecord
        {
            InstanceId = reader.GetString(reader.GetOrdinal("session_runner_instance_id")),
            SessionId = reader.GetInt32(reader.GetOrdinal("session_id")),
            UserName = reader.IsDBNull(reader.GetOrdinal("user_name")) ? null : reader.GetString(reader.GetOrdinal("user_name")),
            SessionType = reader.IsDBNull(reader.GetOrdinal("session_type")) ? SessionType.Unknown : Enum.Parse<SessionType>(reader.GetString(reader.GetOrdinal("session_type")), true),
            ProcessId = reader.IsDBNull(reader.GetOrdinal("process_id")) ? null : reader.GetInt32(reader.GetOrdinal("process_id")),
            Version = reader.IsDBNull(reader.GetOrdinal("version")) ? null : reader.GetString(reader.GetOrdinal("version")),
            Desktop = string.IsNullOrWhiteSpace(desktopJson) ? DesktopState.Unknown : ProtocolJson.Deserialize<DesktopState>(desktopJson) ?? DesktopState.Unknown,
            State = Enum.Parse<SessionRunnerConnectionState>(reader.GetString(reader.GetOrdinal("state")), true),
            RegisteredAtUtc = DateTime.Parse(reader.GetString(reader.GetOrdinal("registered_at_utc"))),
            LastHeartbeatAtUtc = reader.IsDBNull(reader.GetOrdinal("last_heartbeat_at_utc")) ? null : DateTime.Parse(reader.GetString(reader.GetOrdinal("last_heartbeat_at_utc"))),
            DisconnectedAtUtc = reader.IsDBNull(reader.GetOrdinal("disconnected_at_utc")) ? null : DateTime.Parse(reader.GetString(reader.GetOrdinal("disconnected_at_utc"))),
            SessionTokenFingerprint = reader.IsDBNull(reader.GetOrdinal("session_token_fingerprint")) ? null : reader.GetString(reader.GetOrdinal("session_token_fingerprint")),
            SessionTokenExpiresAtUtc = reader.IsDBNull(reader.GetOrdinal("session_token_expires_at_utc")) ? null : DateTime.Parse(reader.GetString(reader.GetOrdinal("session_token_expires_at_utc")))
        };
    }
}
