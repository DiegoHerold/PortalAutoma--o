using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Sessions;
using Biason.AutomationAgent.Infrastructure.Database;

namespace Biason.AutomationAgent.Infrastructure.Persistence;

public sealed class InteractiveSessionRepository : IInteractiveSessionRepository
{
    private readonly SqliteDatabaseManager _db;

    public InteractiveSessionRepository(SqliteDatabaseManager db) => _db = db;

    public async Task UpsertAsync(InteractiveSessionRecord session, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            INSERT INTO interactive_sessions (
                session_id, user_name, domain_name, station_name, session_type, status, is_locked,
                screen_width, screen_height, monitor_count, dpi_scale, session_runner_instance_id, observed_at_utc)
            VALUES ($sid, $user, $domain, $station, $type, $status, $locked, $w, $h, $mon, $dpi, $runner, $obs)
            ON CONFLICT(session_id) DO UPDATE SET
                user_name = excluded.user_name,
                domain_name = excluded.domain_name,
                station_name = excluded.station_name,
                session_type = excluded.session_type,
                status = excluded.status,
                is_locked = excluded.is_locked,
                screen_width = excluded.screen_width,
                screen_height = excluded.screen_height,
                monitor_count = excluded.monitor_count,
                dpi_scale = excluded.dpi_scale,
                session_runner_instance_id = excluded.session_runner_instance_id,
                observed_at_utc = excluded.observed_at_utc;
            """;
        Bind(cmd, session);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task<InteractiveSessionRecord?> GetAsync(int sessionId, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT * FROM interactive_sessions WHERE session_id = $sid;";
        cmd.Parameters.AddWithValue("$sid", sessionId);
        using var reader = await cmd.ExecuteReaderAsync(ct);
        return await reader.ReadAsync(ct) ? Map(reader) : null;
    }

    public async Task<IReadOnlyList<InteractiveSessionRecord>> GetAllAsync(CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT * FROM interactive_sessions ORDER BY session_id;";
        var list = new List<InteractiveSessionRecord>();
        using var reader = await cmd.ExecuteReaderAsync(ct);
        while (await reader.ReadAsync(ct)) list.Add(Map(reader));
        return list;
    }

    public async Task AttachRunnerAsync(int sessionId, string? instanceId, DateTime observedAtUtc, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            UPDATE interactive_sessions
            SET session_runner_instance_id = $iid, observed_at_utc = $obs
            WHERE session_id = $sid;
            """;
        cmd.Parameters.AddWithValue("$iid", (object?)instanceId ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$obs", observedAtUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$sid", sessionId);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    private static void Bind(Microsoft.Data.Sqlite.SqliteCommand cmd, InteractiveSessionRecord s)
    {
        cmd.Parameters.AddWithValue("$sid", s.SessionId);
        cmd.Parameters.AddWithValue("$user", (object?)s.UserName ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$domain", (object?)s.DomainName ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$station", (object?)s.StationName ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$type", s.SessionType.ToString());
        cmd.Parameters.AddWithValue("$status", s.State.ToString());
        cmd.Parameters.AddWithValue("$locked", s.IsLocked.HasValue ? (s.IsLocked.Value ? 1 : 0) : DBNull.Value);
        cmd.Parameters.AddWithValue("$w", s.ScreenWidth.HasValue ? s.ScreenWidth.Value : DBNull.Value);
        cmd.Parameters.AddWithValue("$h", s.ScreenHeight.HasValue ? s.ScreenHeight.Value : DBNull.Value);
        cmd.Parameters.AddWithValue("$mon", s.MonitorCount.HasValue ? s.MonitorCount.Value : DBNull.Value);
        cmd.Parameters.AddWithValue("$dpi", s.DpiScale.HasValue ? s.DpiScale.Value : DBNull.Value);
        cmd.Parameters.AddWithValue("$runner", (object?)s.SessionRunnerInstanceId ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$obs", s.ObservedAtUtc.ToString("o"));
    }

    private static InteractiveSessionRecord Map(Microsoft.Data.Sqlite.SqliteDataReader reader) => new()
    {
        SessionId = reader.GetInt32(reader.GetOrdinal("session_id")),
        UserName = reader.IsDBNull(reader.GetOrdinal("user_name")) ? null : reader.GetString(reader.GetOrdinal("user_name")),
        DomainName = reader.IsDBNull(reader.GetOrdinal("domain_name")) ? null : reader.GetString(reader.GetOrdinal("domain_name")),
        StationName = reader.IsDBNull(reader.GetOrdinal("station_name")) ? null : reader.GetString(reader.GetOrdinal("station_name")),
        SessionType = reader.IsDBNull(reader.GetOrdinal("session_type")) ? SessionType.Unknown : Enum.Parse<SessionType>(reader.GetString(reader.GetOrdinal("session_type")), true),
        State = Enum.Parse<WindowsSessionState>(reader.GetString(reader.GetOrdinal("status")), true),
        IsLocked = reader.IsDBNull(reader.GetOrdinal("is_locked")) ? null : reader.GetInt32(reader.GetOrdinal("is_locked")) != 0,
        ScreenWidth = reader.IsDBNull(reader.GetOrdinal("screen_width")) ? null : reader.GetInt32(reader.GetOrdinal("screen_width")),
        ScreenHeight = reader.IsDBNull(reader.GetOrdinal("screen_height")) ? null : reader.GetInt32(reader.GetOrdinal("screen_height")),
        MonitorCount = reader.IsDBNull(reader.GetOrdinal("monitor_count")) ? null : reader.GetInt32(reader.GetOrdinal("monitor_count")),
        DpiScale = reader.IsDBNull(reader.GetOrdinal("dpi_scale")) ? null : reader.GetDouble(reader.GetOrdinal("dpi_scale")),
        SessionRunnerInstanceId = reader.IsDBNull(reader.GetOrdinal("session_runner_instance_id")) ? null : reader.GetString(reader.GetOrdinal("session_runner_instance_id")),
        ObservedAtUtc = DateTime.Parse(reader.GetString(reader.GetOrdinal("observed_at_utc")))
    };
}
