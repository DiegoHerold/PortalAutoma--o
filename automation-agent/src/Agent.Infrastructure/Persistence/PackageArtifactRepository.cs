using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Models.Storage;
using Biason.AutomationAgent.Infrastructure.Database;

namespace Biason.AutomationAgent.Infrastructure.Persistence;

public sealed class PackageArtifactRepository : IPackageArtifactRepository
{
    private readonly SqliteDatabaseManager _db;
    public PackageArtifactRepository(SqliteDatabaseManager db) => _db = db;

    public async Task SaveAsync(PackageArtifact artifact, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            INSERT OR REPLACE INTO package_artifacts (package_id, automation_id, automation_version_id, version, sha256, size_bytes, store_path, manifest_path, downloaded_at_utc, verified_at_utc, last_used_at_utc, is_valid)
            VALUES ($pid, $aid, $avid, $v, $h, $s, $sp, $mp, $d, $va, $lu, $iv);
            """;
        cmd.Parameters.AddWithValue("$pid", artifact.PackageId);
        cmd.Parameters.AddWithValue("$aid", artifact.AutomationId);
        cmd.Parameters.AddWithValue("$avid", artifact.AutomationVersionId);
        cmd.Parameters.AddWithValue("$v", artifact.Version);
        cmd.Parameters.AddWithValue("$h", artifact.Sha256);
        cmd.Parameters.AddWithValue("$s", artifact.SizeBytes);
        cmd.Parameters.AddWithValue("$sp", artifact.StorePath);
        cmd.Parameters.AddWithValue("$mp", artifact.ManifestPath);
        cmd.Parameters.AddWithValue("$d", artifact.DownloadedAtUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$va", artifact.VerifiedAtUtc?.ToString("o") ?? (object)DBNull.Value);
        cmd.Parameters.AddWithValue("$lu", artifact.LastUsedAtUtc?.ToString("o") ?? (object)DBNull.Value);
        cmd.Parameters.AddWithValue("$iv", artifact.IsValid ? 1 : 0);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task<PackageArtifact?> GetAsync(string packageId, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT * FROM package_artifacts WHERE package_id = $pid;";
        cmd.Parameters.AddWithValue("$pid", packageId);
        using var r = await cmd.ExecuteReaderAsync(ct);
        if (!await r.ReadAsync(ct)) return null;
        return MapPackage(r);
    }

    public async Task<IReadOnlyList<PackageArtifact>> ListAsync(CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT * FROM package_artifacts ORDER BY automation_id, version;";
        var list = new List<PackageArtifact>();
        using var r = await cmd.ExecuteReaderAsync(ct);
        while (await r.ReadAsync(ct)) list.Add(MapPackage(r));
        return list;
    }

    public async Task DeleteAsync(string packageId, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "DELETE FROM package_artifacts WHERE package_id = $pid;";
        cmd.Parameters.AddWithValue("$pid", packageId);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task UpdateLastUsedAsync(string packageId, DateTime lastUsedUtc, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "UPDATE package_artifacts SET last_used_at_utc = $lu WHERE package_id = $pid;";
        cmd.Parameters.AddWithValue("$lu", lastUsedUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$pid", packageId);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task<IReadOnlyList<PackageArtifact>> GetLeastRecentlyUsedAsync(int count, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT * FROM package_artifacts ORDER BY COALESCE(last_used_at_utc, downloaded_at_utc) ASC LIMIT $n;";
        cmd.Parameters.AddWithValue("$n", count);
        var list = new List<PackageArtifact>();
        using var r = await cmd.ExecuteReaderAsync(ct);
        while (await r.ReadAsync(ct)) list.Add(MapPackage(r));
        return list;
    }

    private static PackageArtifact MapPackage(Microsoft.Data.Sqlite.SqliteDataReader r) => new()
    {
        PackageId = r.GetString(r.GetOrdinal("package_id")),
        AutomationId = r.GetString(r.GetOrdinal("automation_id")),
        AutomationVersionId = r.GetString(r.GetOrdinal("automation_version_id")),
        Version = r.GetString(r.GetOrdinal("version")),
        Sha256 = r.GetString(r.GetOrdinal("sha256")),
        SizeBytes = r.GetInt64(r.GetOrdinal("size_bytes")),
        StorePath = r.GetString(r.GetOrdinal("store_path")),
        ManifestPath = r.GetString(r.GetOrdinal("manifest_path")),
        DownloadedAtUtc = DateTime.Parse(r.GetString(r.GetOrdinal("downloaded_at_utc"))),
        VerifiedAtUtc = r.IsDBNull(r.GetOrdinal("verified_at_utc")) ? null : DateTime.Parse(r.GetString(r.GetOrdinal("verified_at_utc"))),
        LastUsedAtUtc = r.IsDBNull(r.GetOrdinal("last_used_at_utc")) ? null : DateTime.Parse(r.GetString(r.GetOrdinal("last_used_at_utc"))),
        IsValid = r.GetInt32(r.GetOrdinal("is_valid")) == 1
    };
}
