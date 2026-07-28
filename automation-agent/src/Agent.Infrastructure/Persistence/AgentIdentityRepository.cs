using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Identity;
using Biason.AutomationAgent.Infrastructure.Database;
using Microsoft.Extensions.Logging;

namespace Biason.AutomationAgent.Infrastructure.Persistence;

public sealed class AgentIdentityRepository : IAgentIdentityService
{
    private readonly SqliteDatabaseManager _db;
    private readonly IClock _clock;
    private readonly ILogger<AgentIdentityRepository> _logger;
    private readonly string _instanceId;
    private AgentIdentity? _cached;

    public AgentIdentityRepository(SqliteDatabaseManager db, IClock clock, ILogger<AgentIdentityRepository> logger)
    {
        _db = db;
        _clock = clock;
        _logger = logger;
        _instanceId = Guid.NewGuid().ToString("N")[..16];
    }

    public async Task<AgentIdentity> GetOrCreateIdentityAsync(CancellationToken ct = default)
    {
        if (_cached is not null)
            return _cached with { InstanceId = _instanceId };

        using var conn = _db.CreateConnection();

        using var selectCmd = conn.CreateCommand();
        selectCmd.CommandText = "SELECT installation_id, agent_id, machine_id, created_at_utc, registered_at_utc FROM agent_identity WHERE id = 1;";

        using var reader = await selectCmd.ExecuteReaderAsync(ct);
        if (await reader.ReadAsync(ct))
        {
            _cached = new AgentIdentity
            {
                InstallationId = reader.GetString(0),
                AgentId = reader.IsDBNull(1) ? null : reader.GetString(1),
                MachineId = reader.GetString(2),
                InstanceId = _instanceId,
                CreatedAtUtc = DateTime.Parse(reader.GetString(3)),
                RegisteredAtUtc = reader.IsDBNull(4) ? null : DateTime.Parse(reader.GetString(4))
            };
            _logger.LogInformation("Loaded existing identity: InstallationId={InstallationId}, MachineId={MachineId}", _cached.InstallationId, _cached.MachineId);
            return _cached;
        }

        reader.Close();

        var installationId = $"ins_{Guid.NewGuid():N}";
        var machineId = GenerateMachineId();
        var now = _clock.UtcNow;

        using var insertCmd = conn.CreateCommand();
        insertCmd.CommandText = """
            INSERT INTO agent_identity (id, installation_id, machine_id, created_at_utc)
            VALUES (1, $iid, $mid, $cat);
            """;
        insertCmd.Parameters.AddWithValue("$iid", installationId);
        insertCmd.Parameters.AddWithValue("$mid", machineId);
        insertCmd.Parameters.AddWithValue("$cat", now.ToString("o"));
        await insertCmd.ExecuteNonQueryAsync(ct);

        _cached = new AgentIdentity
        {
            InstallationId = installationId,
            MachineId = machineId,
            InstanceId = _instanceId,
            CreatedAtUtc = now
        };

        _logger.LogInformation("Created new identity: InstallationId={InstallationId}, MachineId={MachineId}", _cached.InstallationId, _cached.MachineId);
        return _cached;
    }

    public async Task<AgentIdentity?> GetIdentityAsync(CancellationToken ct = default)
    {
        if (_cached is not null)
            return _cached with { InstanceId = _instanceId };

        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT installation_id, agent_id, machine_id, created_at_utc, registered_at_utc FROM agent_identity WHERE id = 1;";

        using var reader = await cmd.ExecuteReaderAsync(ct);
        if (!await reader.ReadAsync(ct))
            return null;

        _cached = new AgentIdentity
        {
            InstallationId = reader.GetString(0),
            AgentId = reader.IsDBNull(1) ? null : reader.GetString(1),
            MachineId = reader.GetString(2),
            InstanceId = _instanceId,
            CreatedAtUtc = DateTime.Parse(reader.GetString(3)),
            RegisteredAtUtc = reader.IsDBNull(4) ? null : DateTime.Parse(reader.GetString(4))
        };
        return _cached;
    }

    public async Task UpdateAgentIdAsync(string agentId, CancellationToken ct = default)
    {
        using var conn = _db.CreateConnection();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "UPDATE agent_identity SET agent_id = $aid, registered_at_utc = $rat WHERE id = 1;";
        cmd.Parameters.AddWithValue("$aid", agentId);
        cmd.Parameters.AddWithValue("$rat", _clock.UtcNow.ToString("o"));
        await cmd.ExecuteNonQueryAsync(ct);

        if (_cached is not null)
        {
            _cached.AgentId = agentId;
            _cached.RegisteredAtUtc = _clock.UtcNow;
        }
    }

    private static string GenerateMachineId()
    {
        var hostname = Environment.MachineName;
        var osSerial = Environment.GetEnvironmentVariable("COMPUTERNAME") ?? hostname;
        var combined = $"{hostname}:{osSerial}:{Environment.ProcessorCount}";
        using var sha = System.Security.Cryptography.SHA256.Create();
        var hash = sha.ComputeHash(System.Text.Encoding.UTF8.GetBytes(combined));
        return $"mch_{Convert.ToHexString(hash[..12]).ToLowerInvariant()}";
    }
}
