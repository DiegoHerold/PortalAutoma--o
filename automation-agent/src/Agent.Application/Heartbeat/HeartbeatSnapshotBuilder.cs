using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Capacity;
using Biason.AutomationAgent.Protocol.Messages;
using Microsoft.Extensions.Options;

namespace Biason.AutomationAgent.Application.Heartbeat;

/// <summary>
/// Compõe o payload de heartbeat a partir de serviços já existentes das Fases 1 e 2.
/// Não coleta nada novo — só agrega o que <see cref="ICapacityManager"/>,
/// <see cref="IResourceMonitor"/>, <see cref="IAgentStateManager"/> e
/// <see cref="IExecutionManager"/> já expõem.
/// </summary>
public sealed class HeartbeatSnapshotBuilder
{
    private readonly IAgentIdentityService _identity;
    private readonly IAgentStateManager _stateManager;
    private readonly ICapacityManager _capacity;
    private readonly IResourceMonitor _resourceMonitor;
    private readonly IExecutionManager _executionManager;
    private readonly IMachineProfileRepository _profileRepo;
    private readonly AgentOptions _agentOptions;

    public HeartbeatSnapshotBuilder(
        IAgentIdentityService identity,
        IAgentStateManager stateManager,
        ICapacityManager capacity,
        IResourceMonitor resourceMonitor,
        IExecutionManager executionManager,
        IMachineProfileRepository profileRepo,
        IOptions<AgentOptions> agentOptions)
    {
        _identity = identity;
        _stateManager = stateManager;
        _capacity = capacity;
        _resourceMonitor = resourceMonitor;
        _executionManager = executionManager;
        _profileRepo = profileRepo;
        _agentOptions = agentOptions.Value;
    }

    public async Task<HeartbeatPayload> BuildAsync(
        Domain.Enums.ConnectionState connectionState,
        int outboxPending,
        int pendingArtifacts,
        CancellationToken ct = default)
    {
        var identity = await _identity.GetIdentityAsync(ct);
        var capacitySnapshot = _capacity.GetSnapshot();
        var resourceMetrics = await _resourceMonitor.GetMetricsAsync(ct);
        var activeExecutions = await _executionManager.GetActiveExecutionsAsync(ct);
        var lastProfile = await _profileRepo.GetLatestAsync(ct);

        var current = resourceMetrics.Current;

        return new HeartbeatPayload
        {
            AgentId = identity?.AgentId,
            InstanceId = identity?.InstanceId ?? "unknown",
            Version = _agentOptions.Version,
            State = _stateManager.CurrentState.ToString().ToUpperInvariant(),
            ConnectionState = connectionState.ToString().ToUpperInvariant(),
            Profile = _agentOptions.Profile,
            LastProfileAtUtc = lastProfile?.CapturedAtUtc,
            Capacity = new HeartbeatCapacity
            {
                Global = BuildGlobalPool(capacitySnapshot),
                Background = BuildPool(capacitySnapshot, PoolType.Background),
                Browser = BuildPool(capacitySnapshot, PoolType.Browser),
                Interactive = BuildPool(capacitySnapshot, PoolType.Interactive)
            },
            Resources = current is null
                ? null
                : new HeartbeatResources
                {
                    CpuPercentage = Math.Round(current.CpuUsagePercent, 1),
                    MemoryPercentage = Math.Round(current.MemoryUsagePercent, 1),
                    DiskFreeMb = current.DiskFreeMb
                },
            // Sem Session Runner (incremento 7+), nunca há sessão interativa disponível.
            InteractiveSession = new HeartbeatInteractiveSession { Available = false },
            RunningExecutions = activeExecutions.Count,
            OutboxPending = outboxPending,
            PendingArtifacts = pendingArtifacts
        };
    }

    private static HeartbeatPoolCapacity BuildGlobalPool(CapacitySnapshot snapshot)
    {
        var total = snapshot.Pools.Values.Sum(p => p.EffectiveTotal);
        var used = snapshot.Pools.Values.Sum(p => p.Used);
        var reserved = snapshot.Pools.Values.Sum(p => p.Reserved);
        return new HeartbeatPoolCapacity { Total = total, Used = used, Reserved = reserved };
    }

    private static HeartbeatPoolCapacity BuildPool(CapacitySnapshot snapshot, PoolType pool)
    {
        if (!snapshot.Pools.TryGetValue(pool, out var capacity))
            return new HeartbeatPoolCapacity { Total = 0, Used = 0 };

        return new HeartbeatPoolCapacity { Total = capacity.EffectiveTotal, Used = capacity.Used, Reserved = capacity.Reserved };
    }
}
