using Biason.AutomationAgent.Domain.Models.Messaging;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface IMessageAcknowledgementRepository
{
    Task SaveAsync(MessageAcknowledgement acknowledgement, CancellationToken ct = default);
}
