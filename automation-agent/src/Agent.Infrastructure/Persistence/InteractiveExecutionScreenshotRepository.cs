using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Models.Interactive;
using Biason.AutomationAgent.Infrastructure.Database;
using Microsoft.Data.Sqlite;

namespace Biason.AutomationAgent.Infrastructure.Persistence;

public sealed class InteractiveExecutionScreenshotRepository : IInteractiveExecutionScreenshotRepository
{
    private readonly SqliteDatabaseManager _db;
    public InteractiveExecutionScreenshotRepository(SqliteDatabaseManager db) => _db = db;

    public async Task AddAsync(InteractiveExecutionScreenshotRecord screenshot, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            INSERT INTO interactive_execution_screenshots (
                artifact_id, execution_id, execution_attempt_id, session_id, reason,
                local_path, captured_at_utc, width, height, sha256, size_bytes)
            VALUES ($artifact, $eid, $aid, $sid, $reason, $path, $captured, $width, $height, $sha, $size);
            """;
        cmd.Parameters.AddWithValue("$artifact", screenshot.ArtifactId);
        cmd.Parameters.AddWithValue("$eid", screenshot.ExecutionId);
        cmd.Parameters.AddWithValue("$aid", screenshot.AttemptId);
        cmd.Parameters.AddWithValue("$sid", screenshot.SessionId);
        cmd.Parameters.AddWithValue("$reason", screenshot.Reason);
        cmd.Parameters.AddWithValue("$path", screenshot.LocalPath);
        cmd.Parameters.AddWithValue("$captured", screenshot.CapturedAtUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$width", screenshot.Width.HasValue ? screenshot.Width.Value : DBNull.Value);
        cmd.Parameters.AddWithValue("$height", screenshot.Height.HasValue ? screenshot.Height.Value : DBNull.Value);
        cmd.Parameters.AddWithValue("$sha", (object?)screenshot.Sha256 ?? DBNull.Value);
        cmd.Parameters.AddWithValue("$size", screenshot.SizeBytes);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task<int> CountByAttemptAsync(string executionId, string attemptId, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT COUNT(*) FROM interactive_execution_screenshots WHERE execution_id = $eid AND execution_attempt_id = $aid;";
        cmd.Parameters.AddWithValue("$eid", executionId);
        cmd.Parameters.AddWithValue("$aid", attemptId);
        return Convert.ToInt32(await cmd.ExecuteScalarAsync(ct));
    }

    public async Task<IReadOnlyList<InteractiveExecutionScreenshotRecord>> GetByAttemptAsync(string executionId, string attemptId, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT * FROM interactive_execution_screenshots WHERE execution_id = $eid AND execution_attempt_id = $aid ORDER BY captured_at_utc;";
        cmd.Parameters.AddWithValue("$eid", executionId);
        cmd.Parameters.AddWithValue("$aid", attemptId);
        return await ReadListAsync(cmd, ct);
    }

    public async Task<IReadOnlyList<InteractiveExecutionScreenshotRecord>> GetAllAsync(CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT * FROM interactive_execution_screenshots ORDER BY captured_at_utc DESC;";
        return await ReadListAsync(cmd, ct);
    }

    private static async Task<IReadOnlyList<InteractiveExecutionScreenshotRecord>> ReadListAsync(SqliteCommand cmd, CancellationToken ct)
    {
        var list = new List<InteractiveExecutionScreenshotRecord>();
        using var r = await cmd.ExecuteReaderAsync(ct);
        while (await r.ReadAsync(ct))
        {
            list.Add(new InteractiveExecutionScreenshotRecord
            {
                ArtifactId = r.GetString(r.GetOrdinal("artifact_id")),
                ExecutionId = r.GetString(r.GetOrdinal("execution_id")),
                AttemptId = r.GetString(r.GetOrdinal("execution_attempt_id")),
                SessionId = r.GetInt32(r.GetOrdinal("session_id")),
                Reason = r.GetString(r.GetOrdinal("reason")),
                LocalPath = r.GetString(r.GetOrdinal("local_path")),
                CapturedAtUtc = DateTime.Parse(r.GetString(r.GetOrdinal("captured_at_utc"))),
                Width = r.IsDBNull(r.GetOrdinal("width")) ? null : r.GetInt32(r.GetOrdinal("width")),
                Height = r.IsDBNull(r.GetOrdinal("height")) ? null : r.GetInt32(r.GetOrdinal("height")),
                Sha256 = r.IsDBNull(r.GetOrdinal("sha256")) ? null : r.GetString(r.GetOrdinal("sha256")),
                SizeBytes = r.GetInt64(r.GetOrdinal("size_bytes"))
            });
        }
        return list;
    }
}
