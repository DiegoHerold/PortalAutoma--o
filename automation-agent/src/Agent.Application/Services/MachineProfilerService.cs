using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace Biason.AutomationAgent.Application.Services;

public sealed class MachineProfilerService : IMachineProfiler
{
    private readonly IOsInfoCollector _osCollector;
    private readonly ICpuInfoCollector _cpuCollector;
    private readonly IMemoryInfoCollector _memoryCollector;
    private readonly IDiskInfoCollector _diskCollector;
    private readonly ISessionInfoCollector _sessionCollector;
    private readonly ISoftwareDetector _softwareDetector;
    private readonly ICapabilityDetector _capabilityDetector;
    private readonly IInteractiveSessionRepository? _interactiveSessions;
    private readonly IClock _clock;
    private readonly AgentOptions _agentOptions;
    private readonly ILogger<MachineProfilerService> _logger;

    public MachineProfilerService(
        IOsInfoCollector osCollector,
        ICpuInfoCollector cpuCollector,
        IMemoryInfoCollector memoryCollector,
        IDiskInfoCollector diskCollector,
        ISessionInfoCollector sessionCollector,
        ISoftwareDetector softwareDetector,
        ICapabilityDetector capabilityDetector,
        IClock clock,
        IOptions<AgentOptions> agentOptions,
        ILogger<MachineProfilerService> logger,
        IInteractiveSessionRepository? interactiveSessions = null)
    {
        _osCollector = osCollector;
        _cpuCollector = cpuCollector;
        _memoryCollector = memoryCollector;
        _diskCollector = diskCollector;
        _sessionCollector = sessionCollector;
        _softwareDetector = softwareDetector;
        _capabilityDetector = capabilityDetector;
        _interactiveSessions = interactiveSessions;
        _clock = clock;
        _agentOptions = agentOptions.Value;
        _logger = logger;
    }

    public async Task<MachineProfileSnapshot> CaptureProfileAsync(CancellationToken ct = default)
    {
        _logger.LogInformation("Capturing machine profile...");

        var os = SafeCollect("OS", () => _osCollector.Collect(), new OsInfo { Name = "Unknown", Architecture = "unknown", Hostname = Environment.MachineName, AgentVersion = _agentOptions.Version });
        var cpu = SafeCollect("CPU", () => _cpuCollector.Collect(), new CpuInfo { Model = "Unknown", Architecture = "unknown", PhysicalCores = Environment.ProcessorCount, LogicalProcessors = Environment.ProcessorCount });
        var memory = SafeCollect("Memory", () => _memoryCollector.Collect(), new MemoryInfo());
        var disk = SafeCollect("Disk", () => _diskCollector.Collect(), new DiskInfo { Volume = "Unknown", DataDirectory = "Unknown" });
        var session = SafeCollect("Session", () => _sessionCollector.Collect(), new SessionInfo { Status = SessionStatus.Unknown, Type = SessionType.Unknown });
        var software = SafeCollect("Software", () => _softwareDetector.DetectAll(), Array.Empty<InstalledSoftware>());
        var capabilities = await SafeCollectAsync("Capabilities", () => _capabilityDetector.DetectAllAsync(ct), Array.Empty<Capability>());
        var interactiveSessions = _interactiveSessions is null
            ? Array.Empty<MachineInteractiveSessionSummary>()
            : (await SafeCollectAsync(
                "InteractiveSessions",
                async () => (await _interactiveSessions.GetAllAsync(ct))
                    .Select(s => new MachineInteractiveSessionSummary
                    {
                        SessionId = s.SessionId,
                        Type = s.SessionType.ToString(),
                        State = s.State.ToString(),
                        Locked = s.IsLocked,
                        RunnerConnected = s.SessionRunnerInstanceId is not null
                    })
                    .ToArray(),
                Array.Empty<MachineInteractiveSessionSummary>()));

        var profileType = RecommendProfile(session);

        var snapshot = new MachineProfileSnapshot
        {
            CapturedAtUtc = _clock.UtcNow,
            Os = os,
            Cpu = cpu,
            Memory = memory,
            Disk = disk,
            Session = session,
            Software = software,
            Capabilities = capabilities,
            InteractiveSessions = interactiveSessions,
            ProfileType = Enum.TryParse<MachineProfileType>(_agentOptions.Profile, ignoreCase: true, out var configured)
                ? configured : profileType
        };

        _logger.LogInformation("Machine profile captured: {Hostname}, CPU={CpuModel}, RAM={RamMb}MB, Profile={Profile}",
            os.Hostname, cpu.Model, memory.TotalMb, snapshot.ProfileType);

        return snapshot;
    }

    private MachineProfileType RecommendProfile(SessionInfo session)
    {
        if (session.Status == SessionStatus.Available)
            return MachineProfileType.Workstation;

        return MachineProfileType.Dedicated;
    }

    private T SafeCollect<T>(string component, Func<T> collector, T fallback)
    {
        try { return collector(); }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to collect {Component} info, using fallback", component);
            return fallback;
        }
    }

    private async Task<T> SafeCollectAsync<T>(string component, Func<Task<T>> collector, T fallback)
    {
        try { return await collector(); }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to collect {Component} info, using fallback", component);
            return fallback;
        }
    }
}
