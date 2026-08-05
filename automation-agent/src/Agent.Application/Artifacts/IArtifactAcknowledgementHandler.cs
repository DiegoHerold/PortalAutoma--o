using Biason.AutomationAgent.Domain.Models.Messaging;
using Biason.AutomationAgent.Protocol.Messages;

namespace Biason.AutomationAgent.Application.Artifacts;

public interface IArtifactAcknowledgementHandler
{
    Task HandleAsync(
        OutboxMessage originalMessage,
        MessageAcknowledgementPayload acknowledgement,
        DateTime nowUtc,
        CancellationToken ct = default);
}
