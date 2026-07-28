using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Models;
using Biason.AutomationAgent.Infrastructure.Database;
using Microsoft.Extensions.Logging;

namespace Biason.AutomationAgent.Infrastructure.Persistence;

public sealed class ResourceSampleRepository : IResourceSampleRepository
{
    private readonly SqliteDatabaseManager _db;
    private readonly ILogger<ResourceSampleRepository> _logger;

    public ResourceSampleRepository(SqliteDatabaseManager db, ILogger<ResourceSampleRepository> logger)
    {
        _db = db;
        _logger = logger;
    }

    public async Task SaveAsync(ResourceSample sample, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            INSERT INTO resource_samples
            (sampled_at_utc, cpu_usage_percent, memory_total_mb, memory_available_mb, memory_used_mb,
             memory_usage_percent, disk_total_mb, disk_free_mb, disk_usage_percent, agent_memory_mb,
             process_count, uptime_seconds, database_size_kb, logs_size_kb, spool_size_kb, cache_size_kb, session_status)
            VALUES ($s, $cpu, $mt, $ma, $mu, $mp, $dt, $df, $dp, $am, $pc, $up, $db, $lg, $sp, $ca, $ss);
            """;
        cmd.Parameters.AddWithValue("$s", sample.SampledAtUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$cpu", sample.CpuUsagePercent);
        cmd.Parameters.AddWithValue("$mt", sample.MemoryTotalMb);
        cmd.Parameters.AddWithValue("$ma", sample.MemoryAvailableMb);
        cmd.Parameters.AddWithValue("$mu", sample.MemoryUsedMb);
        cmd.Parameters.AddWithValue("$mp", sample.MemoryUsagePercent);
        cmd.Parameters.AddWithValue("$dt", sample.DiskTotalMb);
        cmd.Parameters.AddWithValue("$df", sample.DiskFreeMb);
        cmd.Parameters.AddWithValue("$dp", sample.DiskUsagePercent);
        cmd.Parameters.AddWithValue("$am", sample.AgentMemoryMb);
        cmd.Parameters.AddWithValue("$pc", sample.ProcessCount);
        cmd.Parameters.AddWithValue("$up", sample.UptimeSeconds);
        cmd.Parameters.AddWithValue("$db", sample.DatabaseSizeKb);
        cmd.Parameters.AddWithValue("$lg", sample.LogsSizeKb);
        cmd.Parameters.AddWithValue("$sp", sample.SpoolSizeKb);
        cmd.Parameters.AddWithValue("$ca", sample.CacheSizeKb);
        cmd.Parameters.AddWithValue("$ss", (object?)sample.SessionStatus ?? DBNull.Value);
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task<IReadOnlyList<ResourceSample>> GetRecentAsync(int minutes, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            SELECT id, sampled_at_utc, cpu_usage_percent, memory_total_mb, memory_available_mb,
                   memory_used_mb, memory_usage_percent, disk_total_mb, disk_free_mb, disk_usage_percent,
                   agent_memory_mb, process_count, uptime_seconds, database_size_kb, logs_size_kb,
                   spool_size_kb, cache_size_kb, session_status
            FROM resource_samples
            WHERE sampled_at_utc >= datetime('now', $min)
            ORDER BY sampled_at_utc DESC;
            """;
        cmd.Parameters.AddWithValue("$min", $"-{minutes} minutes");

        var results = new List<ResourceSample>();
        using var reader = await cmd.ExecuteReaderAsync(ct);
        while (await reader.ReadAsync(ct))
        {
            results.Add(ReadSample(reader));
        }
        return results;
    }

    public async Task<ResourceSample?> GetLatestAsync(CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            SELECT id, sampled_at_utc, cpu_usage_percent, memory_total_mb, memory_available_mb,
                   memory_used_mb, memory_usage_percent, disk_total_mb, disk_free_mb, disk_usage_percent,
                   agent_memory_mb, process_count, uptime_seconds, database_size_kb, logs_size_kb,
                   spool_size_kb, cache_size_kb, session_status
            FROM resource_samples ORDER BY sampled_at_utc DESC LIMIT 1;
            """;
        using var reader = await cmd.ExecuteReaderAsync(ct);
        return await reader.ReadAsync(ct) ? ReadSample(reader) : null;
    }

    public async Task PurgeOlderThanAsync(DateTime cutoff, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "DELETE FROM resource_samples WHERE sampled_at_utc < $cutoff;";
        cmd.Parameters.AddWithValue("$cutoff", cutoff.ToString("o"));
        var deleted = await cmd.ExecuteNonQueryAsync(ct);
        if (deleted > 0)
            _logger.LogDebug("Purged {Count} old resource samples", deleted);
    }

    private static ResourceSample ReadSample(Microsoft.Data.Sqlite.SqliteDataReader r) => new()
    {
        Id = r.GetInt64(0),
        SampledAtUtc = DateTime.Parse(r.GetString(1)),
        CpuUsagePercent = r.GetDouble(2),
        MemoryTotalMb = r.GetInt64(3),
        MemoryAvailableMb = r.GetInt64(4),
        MemoryUsedMb = r.GetInt64(5),
        MemoryUsagePercent = r.GetDouble(6),
        DiskTotalMb = r.GetInt64(7),
        DiskFreeMb = r.GetInt64(8),
        DiskUsagePercent = r.GetDouble(9),
        AgentMemoryMb = r.GetInt64(10),
        ProcessCount = r.GetInt32(11),
        UptimeSeconds = r.GetInt64(12),
        DatabaseSizeKb = r.GetInt64(13),
        LogsSizeKb = r.GetInt64(14),
        SpoolSizeKb = r.GetInt64(15),
        CacheSizeKb = r.GetInt64(16),
        SessionStatus = r.IsDBNull(17) ? null : r.GetString(17)
    };
}
