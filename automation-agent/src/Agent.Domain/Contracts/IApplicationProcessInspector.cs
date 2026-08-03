using Biason.AutomationAgent.Domain.Models.Interactive;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface IApplicationProcessInspector
{
    Task<IReadOnlyList<ApplicationProcessCandidate>> FindExistingAsync(string applicationKey, int sessionId, CancellationToken ct = default);
}
