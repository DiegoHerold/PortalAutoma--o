using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Models.Messaging;
using Biason.AutomationAgent.Protocol.Messages;

namespace Biason.AutomationAgent.Application.Messaging.Handlers;

public sealed class AgentSyncRequestHandler : IInboxCommandHandler
{
    private readonly IAgentSyncService _syncService;

    public AgentSyncRequestHandler(IAgentSyncService syncService)
    {
        _syncService = syncService;
    }

    public string MessageType => PortalMessageTypes.SyncRequest;

    public async Task<InboxCommandHandlerResult> HandleAsync(InboxCommand command, CancellationToken ct = default)
    {
        await _syncService.PublishSyncStateAsync("portal_request", correlationId: command.MessageId, ct: ct);
        return InboxCommandHandlerResult.Processed("sync_state_enqueued");
    }
}
