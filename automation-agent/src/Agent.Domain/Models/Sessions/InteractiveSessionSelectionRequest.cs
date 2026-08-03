using Biason.AutomationAgent.Domain.Enums;

namespace Biason.AutomationAgent.Domain.Models.Sessions;

public sealed class InteractiveSessionSelectionRequest
{
    public InteractiveSessionSelectionPolicy Policy { get; init; }
    public int? SessionId { get; init; }
}
