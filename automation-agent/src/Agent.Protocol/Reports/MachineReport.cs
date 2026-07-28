using System.Text.Json.Serialization;

namespace Biason.AutomationAgent.Protocol.Reports;

public sealed class MachineReport
{
    [JsonPropertyName("protocol_version")]
    public string ProtocolVersion { get; init; } = "1.0";

    [JsonPropertyName("agent")]
    public AgentSection Agent { get; init; } = default!;

    [JsonPropertyName("machine")]
    public MachineSection Machine { get; init; } = default!;

    [JsonPropertyName("interactive_session")]
    public SessionSection InteractiveSession { get; init; } = default!;

    [JsonPropertyName("capabilities")]
    public IReadOnlyList<CapabilityEntry> Capabilities { get; init; } = Array.Empty<CapabilityEntry>();

    [JsonPropertyName("monitoring")]
    public MonitoringSection Monitoring { get; init; } = default!;
}

public sealed class AgentSection
{
    [JsonPropertyName("installation_id")]
    public string InstallationId { get; init; } = default!;

    [JsonPropertyName("agent_id")]
    public string? AgentId { get; init; }

    [JsonPropertyName("instance_id")]
    public string InstanceId { get; init; } = default!;

    [JsonPropertyName("version")]
    public string Version { get; init; } = default!;

    [JsonPropertyName("state")]
    public string State { get; init; } = default!;

    [JsonPropertyName("profile")]
    public string Profile { get; init; } = default!;
}

public sealed class MachineSection
{
    [JsonPropertyName("hostname")]
    public string Hostname { get; init; } = default!;

    [JsonPropertyName("operating_system")]
    public OsSection OperatingSystem { get; init; } = default!;

    [JsonPropertyName("cpu")]
    public CpuSection Cpu { get; init; } = default!;

    [JsonPropertyName("memory")]
    public MemorySection Memory { get; init; } = default!;

    [JsonPropertyName("disk")]
    public DiskSection Disk { get; init; } = default!;
}

public sealed class OsSection
{
    [JsonPropertyName("name")]
    public string Name { get; init; } = default!;

    [JsonPropertyName("build")]
    public string? Build { get; init; }

    [JsonPropertyName("architecture")]
    public string Architecture { get; init; } = default!;
}

public sealed class CpuSection
{
    [JsonPropertyName("model")]
    public string Model { get; init; } = default!;

    [JsonPropertyName("physical_cores")]
    public int PhysicalCores { get; init; }

    [JsonPropertyName("logical_processors")]
    public int LogicalProcessors { get; init; }

    [JsonPropertyName("current_usage_percentage")]
    public double? CurrentUsagePercentage { get; init; }
}

public sealed class MemorySection
{
    [JsonPropertyName("total_mb")]
    public long TotalMb { get; init; }

    [JsonPropertyName("available_mb")]
    public long AvailableMb { get; init; }

    [JsonPropertyName("usage_percentage")]
    public double UsagePercentage { get; init; }
}

public sealed class DiskSection
{
    [JsonPropertyName("total_mb")]
    public long TotalMb { get; init; }

    [JsonPropertyName("free_mb")]
    public long FreeMb { get; init; }

    [JsonPropertyName("usage_percentage")]
    public double UsagePercentage { get; init; }
}

public sealed class SessionSection
{
    [JsonPropertyName("status")]
    public string Status { get; init; } = default!;

    [JsonPropertyName("locked")]
    public bool? Locked { get; init; }

    [JsonPropertyName("user")]
    public string? User { get; init; }

    [JsonPropertyName("session_id")]
    public int? SessionId { get; init; }

    [JsonPropertyName("type")]
    public string Type { get; init; } = default!;
}

public sealed class CapabilityEntry
{
    [JsonPropertyName("key")]
    public string Key { get; init; } = default!;

    [JsonPropertyName("status")]
    public string Status { get; init; } = default!;

    [JsonPropertyName("version")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public string? Version { get; init; }

    [JsonPropertyName("source")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public string? Source { get; init; }

    [JsonPropertyName("detected_at")]
    public DateTime DetectedAt { get; init; }

    [JsonPropertyName("details")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public Dictionary<string, string>? Details { get; init; }
}

public sealed class MonitoringSection
{
    [JsonPropertyName("sampled_at")]
    public DateTime SampledAt { get; init; }

    [JsonPropertyName("agent_memory_mb")]
    public long AgentMemoryMb { get; init; }

    [JsonPropertyName("process_count")]
    public int ProcessCount { get; init; }
}
