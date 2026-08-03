using Biason.AutomationAgent.Domain.Models.Messaging;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface IOutboxRepository
{
    Task<OutboxMessage> EnqueueAsync(OutboxMessageDraft draft, CancellationToken ct = default);
    Task<OutboxMessage?> GetByMessageIdAsync(string messageId, CancellationToken ct = default);
    Task<IReadOnlyList<OutboxMessage>> GetReadyBatchAsync(int maxCount, DateTime nowUtc, CancellationToken ct = default);
    Task MarkSentAsync(long id, DateTime sentAtUtc, CancellationToken ct = default);
    Task MarkFailedAsync(long id, DateTime availableAtUtc, string error, CancellationToken ct = default);
    Task MarkDeadLetterAsync(long id, DateTime nowUtc, string error, CancellationToken ct = default);
    Task MarkAcknowledgedAsync(string messageId, DateTime acknowledgedAtUtc, string? detail = null, CancellationToken ct = default);
    Task<int> MarkAcknowledgedThroughSequenceAsync(string executionAttemptId, long lastContiguousSequence, DateTime acknowledgedAtUtc, string? detail = null, CancellationToken ct = default);
    Task<int> RecoverTimedOutAsync(DateTime nowUtc, TimeSpan acknowledgementTimeout, int maxAttempts, CancellationToken ct = default);
    Task<int> CountPendingAsync(CancellationToken ct = default);
    Task<OutboxDiagnostics> GetDiagnosticsAsync(CancellationToken ct = default);
}
