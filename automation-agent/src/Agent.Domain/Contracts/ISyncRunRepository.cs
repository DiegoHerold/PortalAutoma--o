using Biason.AutomationAgent.Domain.Models.Execution;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface ISyncRunRepository
{
    Task SaveAsync(SyncRunRecord run, CancellationToken ct = default);
    Task CompleteAsync(SyncRunRecord run, CancellationToken ct = default);
    Task<SyncRunRecord?> GetLatestAsync(CancellationToken ct = default);
}
