using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Protocol.Messages;
using Microsoft.Extensions.Logging;

namespace Biason.AutomationAgent.Application.Messaging;

public sealed class AgentInventoryPublisher
{
    private readonly ICapabilityRepository _capabilities;
    private readonly IAgentIdentityService _identity;
    private readonly OutboxMessagePublisher _outboxPublisher;
    private readonly IClock _clock;
    private readonly ILogger<AgentInventoryPublisher> _logger;

    public AgentInventoryPublisher(
        ICapabilityRepository capabilities,
        IAgentIdentityService identity,
        OutboxMessagePublisher outboxPublisher,
        IClock clock,
        ILogger<AgentInventoryPublisher> logger)
    {
        _capabilities = capabilities;
        _identity = identity;
        _outboxPublisher = outboxPublisher;
        _clock = clock;
        _logger = logger;
    }

    public async Task PublishCapabilitiesAsync(string reason, CancellationToken ct = default)
    {
        var identity = await _identity.GetIdentityAsync(ct);
        if (identity is null || !identity.IsRegistered)
        {
            _logger.LogDebug("Skipping capability publication: Agent is not registered.");
            return;
        }

        var capabilities = await _capabilities.GetAllAsync(ct);
        var observedAt = _clock.UtcNow;
        var payload = new
        {
            agent_id = identity.AgentId,
            agent_instance_id = identity.InstanceId,
            observed_at = observedAt,
            reason,
            capabilities = capabilities.Select(capability => new
            {
                key = capability.Key,
                status = capability.Status,
                version = capability.Version,
                source = capability.Source,
                observed_at = capability.DetectedAtUtc,
                attributes = capability.Details ?? new Dictionary<string, string>()
            }).ToArray()
        };

        await _outboxPublisher.EnqueueAsync(
            PortalMessageTypes.CapabilitiesUpdated,
            payload,
            correlationId: $"cap_{Guid.NewGuid():N}",
            ct: ct);

        _logger.LogInformation(
            "Published {Count} capability(ies) to Portal outbox ({Reason}).",
            capabilities.Count,
            reason);
    }
}
