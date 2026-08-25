using System.Collections.Concurrent;

namespace Biason.AutomationAgent.Application.Messaging;

public sealed class ExecutionAttemptSequenceTracker
{
    private readonly ConcurrentDictionary<string, long> _sequences = new(StringComparer.Ordinal);

    public long Next(string executionAttemptId)
    {
        if (string.IsNullOrWhiteSpace(executionAttemptId))
            throw new ArgumentException("ExecutionAttemptId is required for sequenced events.", nameof(executionAttemptId));

        return _sequences.AddOrUpdate(executionAttemptId, 1, (_, current) => current + 1);
    }
}
