using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Models;
using Biason.AutomationAgent.Protocol.Reports;

namespace Biason.AutomationAgent.Application.Services;

public sealed class MachineReportGenerator
{
    private readonly IAgentIdentityService _identity;
    private readonly IAgentStateManager _stateManager;
    private readonly IMachineProfiler _profiler;
    private readonly IResourceMonitor _monitor;
    private readonly IClock _clock;

    public MachineReportGenerator(
        IAgentIdentityService identity,
        IAgentStateManager stateManager,
        IMachineProfiler profiler,
        IResourceMonitor monitor,
        IClock clock)
    {
        _identity = identity;
        _stateManager = stateManager;
        _profiler = profiler;
        _monitor = monitor;
        _clock = clock;
    }

    public async Task<MachineReport> GenerateAsync(CancellationToken ct = default)
    {
        var id = await _identity.GetOrCreateIdentityAsync(ct);
        var profile = await _profiler.CaptureProfileAsync(ct);
        var metrics = await _monitor.GetMetricsAsync(ct);

        return new MachineReport
        {
            Agent = new AgentSection
            {
                InstallationId = id.InstallationId,
                AgentId = id.AgentId,
                InstanceId = id.InstanceId,
                Version = profile.Os.AgentVersion,
                State = _stateManager.CurrentState.ToString().ToUpperInvariant(),
                Profile = profile.ProfileType.ToString().ToLowerInvariant()
            },
            Machine = new MachineSection
            {
                Hostname = profile.Os.Hostname,
                OperatingSystem = new OsSection
                {
                    Name = profile.Os.Name,
                    Build = profile.Os.Build,
                    Architecture = profile.Os.Architecture
                },
                Cpu = new CpuSection
                {
                    Model = profile.Cpu.Model,
                    PhysicalCores = profile.Cpu.PhysicalCores,
                    LogicalProcessors = profile.Cpu.LogicalProcessors,
                    CurrentUsagePercentage = metrics.Current?.CpuUsagePercent
                },
                Memory = new MemorySection
                {
                    TotalMb = profile.Memory.TotalMb,
                    AvailableMb = profile.Memory.AvailableMb,
                    UsagePercentage = profile.Memory.UsagePercent
                },
                Disk = new DiskSection
                {
                    TotalMb = profile.Disk.TotalMb,
                    FreeMb = profile.Disk.FreeMb,
                    UsagePercentage = profile.Disk.UsagePercent
                }
            },
            InteractiveSession = new SessionSection
            {
                Status = profile.Session.Status.ToString().ToLowerInvariant(),
                Locked = profile.Session.IsLocked,
                User = profile.Session.User,
                SessionId = profile.Session.SessionId,
                Type = profile.Session.Type.ToString().ToLowerInvariant()
            },
            Capabilities = profile.Capabilities.Select(c => new CapabilityEntry
            {
                Key = c.Key,
                Status = c.Status.ToString().ToLowerInvariant(),
                Version = c.Version,
                Source = c.Source,
                DetectedAt = c.DetectedAtUtc,
                Details = c.Details
            }).ToList(),
            Monitoring = new MonitoringSection
            {
                SampledAt = metrics.Current?.SampledAtUtc ?? _clock.UtcNow,
                AgentMemoryMb = metrics.Current?.AgentMemoryMb ?? 0,
                ProcessCount = metrics.Current?.ProcessCount ?? 0
            }
        };
    }
}
