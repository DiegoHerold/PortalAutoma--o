using System.Text.Json;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Models;
using Biason.AutomationAgent.Infrastructure.Database;

namespace Biason.AutomationAgent.Infrastructure.Persistence;

public sealed class MachineProfileRepository : IMachineProfileRepository
{
    private readonly SqliteDatabaseManager _db;
    private static readonly JsonSerializerOptions JsonOpts = new() { PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower, WriteIndented = false };

    public MachineProfileRepository(SqliteDatabaseManager db) => _db = db;

    public async Task SaveAsync(MachineProfileSnapshot profile, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            INSERT INTO machine_profiles (captured_at_utc, profile_json)
            VALUES ($c, $p);
            """;
        cmd.Parameters.AddWithValue("$c", profile.CapturedAtUtc.ToString("o"));
        cmd.Parameters.AddWithValue("$p", JsonSerializer.Serialize(profile, JsonOpts));
        await cmd.ExecuteNonQueryAsync(ct);
    }

    public async Task<MachineProfileSnapshot?> GetLatestAsync(CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT profile_json FROM machine_profiles ORDER BY captured_at_utc DESC LIMIT 1;";
        var result = await cmd.ExecuteScalarAsync(ct);
        return result is string json ? JsonSerializer.Deserialize<MachineProfileSnapshot>(json, JsonOpts) : null;
    }
}
