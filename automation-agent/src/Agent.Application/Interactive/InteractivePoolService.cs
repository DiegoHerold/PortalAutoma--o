using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Contracts;
using Microsoft.Extensions.Options;

namespace Biason.AutomationAgent.Application.Interactive;

public sealed class InteractivePoolService : IInteractivePoolService
{
    private readonly IInteractiveExecutionAssignmentRepository _assignments;
    private readonly InteractivePoolOptions _options;

    public InteractivePoolService(
        IInteractiveExecutionAssignmentRepository assignments,
        IOptions<InteractivePoolOptions> options)
    {
        _assignments = assignments;
        _options = options.Value;
    }

    public async Task<bool> HasSlotAsync(int sessionId, CancellationToken ct = default)
    {
        var global = await CountActiveAsync(ct);
        if (global >= _options.GlobalSlots)
            return false;

        var session = await CountActiveBySessionAsync(sessionId, ct);
        return session < _options.PerSessionSlots;
    }

    public Task<int> CountActiveAsync(CancellationToken ct = default) =>
        _assignments.CountActiveAsync(ct);

    public Task<int> CountActiveBySessionAsync(int sessionId, CancellationToken ct = default) =>
        _assignments.CountActiveBySessionAsync(sessionId, ct);
}
