using System.Text.Json;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models;
using Biason.AutomationAgent.Infrastructure.Database;

namespace Biason.AutomationAgent.Infrastructure.Persistence;

public sealed class CapabilityRepository : ICapabilityRepository
{
    private readonly SqliteDatabaseManager _db;

    public CapabilityRepository(SqliteDatabaseManager db) => _db = db;

    public async Task SaveAllAsync(IReadOnlyList<Capability> capabilities, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var tx = conn.BeginTransaction();
        try
        {
            var delCmd = conn.CreateCommand();
            delCmd.Transaction = tx;
            delCmd.CommandText = "DELETE FROM capabilities;";
            await delCmd.ExecuteNonQueryAsync(ct);

            foreach (var cap in capabilities)
            {
                var cmd = conn.CreateCommand();
                cmd.Transaction = tx;
                cmd.CommandText = """
                    INSERT INTO capabilities (key, status, version, source, detected_at_utc, details_json)
                    VALUES ($k, $s, $v, $src, $d, $dj);
                    """;
                cmd.Parameters.AddWithValue("$k", cap.Key);
                cmd.Parameters.AddWithValue("$s", cap.Status.ToString().ToLowerInvariant());
                cmd.Parameters.AddWithValue("$v", (object?)cap.Version ?? DBNull.Value);
                cmd.Parameters.AddWithValue("$src", (object?)cap.Source ?? DBNull.Value);
                cmd.Parameters.AddWithValue("$d", cap.DetectedAtUtc.ToString("o"));
                cmd.Parameters.AddWithValue("$dj", cap.Details is not null ? JsonSerializer.Serialize(cap.Details) : DBNull.Value);
                await cmd.ExecuteNonQueryAsync(ct);
            }

            tx.Commit();
        }
        catch
        {
            tx.Rollback();
            throw;
        }
    }

    public async Task<IReadOnlyList<Capability>> GetAllAsync(CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT key, status, version, source, detected_at_utc, details_json FROM capabilities;";

        var results = new List<Capability>();
        using var reader = await cmd.ExecuteReaderAsync(ct);
        while (await reader.ReadAsync(ct))
        {
            results.Add(new Capability
            {
                Key = reader.GetString(0),
                Status = Enum.Parse<CapabilityStatus>(reader.GetString(1), ignoreCase: true),
                Version = reader.IsDBNull(2) ? null : reader.GetString(2),
                Source = reader.IsDBNull(3) ? null : reader.GetString(3),
                DetectedAtUtc = DateTime.Parse(reader.GetString(4)),
                Details = reader.IsDBNull(5) ? null : JsonSerializer.Deserialize<Dictionary<string, string>>(reader.GetString(5))
            });
        }
        return results;
    }
}
