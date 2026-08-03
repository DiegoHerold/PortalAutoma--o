using Biason.AutomationAgent.Domain.Models.Messaging;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface IInboxRepository
{
    Task<InboxStoreResult> StoreReceivedAsync(InboxCommandDraft draft, CancellationToken ct = default);
    Task<InboxCommand?> GetByMessageIdAsync(string messageId, CancellationToken ct = default);
    Task<IReadOnlyList<InboxCommand>> GetPendingBatchAsync(int maxCount, CancellationToken ct = default);
    Task MarkProcessingAsync(long id, CancellationToken ct = default);
    Task MarkProcessedAsync(long id, DateTime processedAtUtc, string? result, CancellationToken ct = default);
    Task MarkPendingAsync(long id, string error, CancellationToken ct = default);
    Task MarkDeadLetterAsync(long id, DateTime nowUtc, string error, CancellationToken ct = default);
    Task<int> CountPendingAsync(CancellationToken ct = default);
    Task<InboxDiagnostics> GetDiagnosticsAsync(CancellationToken ct = default);
}
