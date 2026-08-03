using Biason.AutomationAgent.Domain.Models.Sessions;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface IInteractiveSessionSelector
{
    Task<InteractiveSessionSelectionResult> SelectAsync(InteractiveSessionSelectionRequest request, CancellationToken ct = default);
}
