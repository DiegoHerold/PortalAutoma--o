using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Models.Storage;
using Biason.AutomationAgent.Infrastructure.Database;

namespace Biason.AutomationAgent.Infrastructure.Persistence;

public sealed class RuntimeArtifactRepository : IRuntimeArtifactRepository
{
    private readonly SqliteDatabaseManager _db;
    public RuntimeArtifactRepository(SqliteDatabaseManager db) => _db = db;

    public async Task SaveAsync(RuntimeArtifact artifact, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            INSERT OR REPLACE INTO runtime_artifacts (runtime_id, version, platform, sha256, size_bytes, store_path, downloaded_at_utc, verified_at_utc, is_valid)
            VALUES ($rid, $v, $p, $h, $s, $sp, $d, $va, $iv);
            """;
        cmd.Parameters.AddWithValue("$rid", artifact.RuntimeId);
        cmd.Parameters.AddWithValue("$v", artifact.Version);
        cmd.Parameters.AddWithValue("$p", artifact.Platform);
        cmd.Parameters.AddWithValue("$h", artifact.Sha256);
        cmd.Parameters.AddWithValue("$s", artifact.SizeBytes);
        cmd.Parameters.AddWithValue("$sp", artifact.StorePath);
        cmd.Parameters.AddWithValue("$d", artifact.DownloadedAtUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$va", artifact.VerifiedAtUtc?.ToString("o") ?? (object)DBNull.Value);
        cmd.Parameters.AddWithValue("$iv", artifact.IsValid ? 1 : 0);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task<RuntimeArtifact?> GetAsync(string runtimeId, string version, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT * FROM runtime_artifacts WHERE runtime_id = $rid AND version = $v;";
        cmd.Parameters.AddWithValue("$rid", runtimeId);
        cmd.Parameters.AddWithValue("$v", version);
        using var r = await cmd.ExecuteReaderAsync(ct);
        if (!await r.ReadAsync(ct)) return null;
        return MapRuntime(r);
    }

    public async Task<IReadOnlyList<RuntimeArtifact>> ListAsync(CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT * FROM runtime_artifacts ORDER BY runtime_id, version;";
        var list = new List<RuntimeArtifact>();
        using var r = await cmd.ExecuteReaderAsync(ct);
        while (await r.ReadAsync(ct)) list.Add(MapRuntime(r));
        return list;
    }

    public async Task DeleteAsync(string runtimeId, string version, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "DELETE FROM runtime_artifacts WHERE runtime_id = $rid AND version = $v;";
        cmd.Parameters.AddWithValue("$rid", runtimeId);
        cmd.Parameters.AddWithValue("$v", version);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    private static RuntimeArtifact MapRuntime(Microsoft.Data.Sqlite.SqliteDataReader r) => new()
    {
        RuntimeId = r.GetString(r.GetOrdinal("runtime_id")),
        Version = r.GetString(r.GetOrdinal("version")),
        Platform = r.GetString(r.GetOrdinal("platform")),
        Sha256 = r.GetString(r.GetOrdinal("sha256")),
        SizeBytes = r.GetInt64(r.GetOrdinal("size_bytes")),
        StorePath = r.GetString(r.GetOrdinal("store_path")),
        DownloadedAtUtc = DateTime.Parse(r.GetString(r.GetOrdinal("downloaded_at_utc"))),
        VerifiedAtUtc = r.IsDBNull(r.GetOrdinal("verified_at_utc")) ? null : DateTime.Parse(r.GetString(r.GetOrdinal("verified_at_utc"))),
        IsValid = r.GetInt32(r.GetOrdinal("is_valid")) == 1
    };
}
