using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Capacity;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace Biason.AutomationAgent.Application.Capacity;

public sealed class CapacityManager : ICapacityManager
{
    private readonly CapacityOptions _options;
    private readonly IAgentIdentityService _identity;
    private readonly IClock _clock;
    private readonly ILogger<CapacityManager> _logger;
    private readonly object _lock = new();
    private readonly Dictionary<PoolType, PoolCapacity> _pools;
    private int _revision;

    public CapacityManager(
        IOptions<CapacityOptions> options,
        IAgentIdentityService identity,
        IClock clock,
        ILogger<CapacityManager> logger)
    {
        _options = options.Value;
        _identity = identity;
        _clock = clock;
        _logger = logger;

        _pools = new Dictionary<PoolType, PoolCapacity>
        {
            [PoolType.Background] = new PoolCapacity
            {
                RecommendedTotal = _options.BackgroundPoolSize,
                AdministratorTotal = _options.BackgroundPoolSize,
                EffectiveTotal = _options.BackgroundPoolSize
            },
            [PoolType.Browser] = new PoolCapacity
            {
                RecommendedTotal = _options.BrowserPoolSize,
                AdministratorTotal = _options.BrowserPoolSize,
                EffectiveTotal = _options.BrowserPoolSize
            },
            [PoolType.Interactive] = new PoolCapacity
            {
                RecommendedTotal = _options.InteractivePoolSize,
                AdministratorTotal = _options.InteractivePoolSize,
                EffectiveTotal = _options.InteractivePoolSize
            }
        };
    }

    public CapacitySnapshot GetSnapshot()
    {
        lock (_lock)
        {
            _revision++;
            var identity = _identity.GetCachedIdentity();
            return new CapacitySnapshot
            {
                AgentId = identity?.AgentId ?? identity?.InstallationId ?? "unknown",
                AgentInstanceId = identity?.InstanceId ?? "unknown",
                ObservedAt = _clock.UtcNow,
                Revision = _revision,
                TtlSeconds = _options.SnapshotTtlSeconds,
                Pools = new Dictionary<PoolType, PoolCapacity>(_pools)
            };
        }
    }

    public PoolCapacity GetPoolCapacity(PoolType pool)
    {
        lock (_lock) { return _pools[pool]; }
    }

    public bool HasAvailableSlots(PoolType pool, int slotsNeeded = 1)
    {
        lock (_lock) { return _pools[pool].Available >= slotsNeeded; }
    }

    public void IncrementUsed(PoolType pool, int slots = 1)
    {
        lock (_lock)
        {
            _pools[pool].Used += slots;
            _logger.LogDebug("Pool {Pool}: used={Used}, reserved={Reserved}, available={Available}",
                pool, _pools[pool].Used, _pools[pool].Reserved, _pools[pool].Available);
        }
    }

    public void DecrementUsed(PoolType pool, int slots = 1)
    {
        lock (_lock)
        {
            _pools[pool].Used = Math.Max(0, _pools[pool].Used - slots);
        }
    }
}
