using Biason.AutomationAgent.Domain.Enums;

namespace Biason.AutomationAgent.Domain.Models;

public sealed class MachineProfileSnapshot
{
    public long Id { get; init; }
    public DateTime CapturedAtUtc { get; init; }
    public OsInfo Os { get; init; } = default!;
    public CpuInfo Cpu { get; init; } = default!;
    public MemoryInfo Memory { get; init; } = default!;
    public DiskInfo Disk { get; init; } = default!;
    public SessionInfo Session { get; init; } = default!;
    public IReadOnlyList<InstalledSoftware> Software { get; init; } = Array.Empty<InstalledSoftware>();
    public IReadOnlyList<Capability> Capabilities { get; init; } = Array.Empty<Capability>();
    public IReadOnlyList<MachineInteractiveSessionSummary> InteractiveSessions { get; init; } = Array.Empty<MachineInteractiveSessionSummary>();
    public MachineProfileType ProfileType { get; init; }
}

public sealed class MachineInteractiveSessionSummary
{
    public int SessionId { get; init; }
    public string? Type { get; init; }
    public string? State { get; init; }
    public bool? Locked { get; init; }
    public bool RunnerConnected { get; init; }
}
