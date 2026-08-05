using Biason.AutomationAgent.Application.Execution;
using Biason.AutomationAgent.Protocol.Messages;

namespace Biason.AutomationAgent.Application.Messaging;

public sealed class OutboxExecutionLifecyclePublisher : IExecutionLifecyclePublisher
{
    private readonly OutboxMessagePublisher _outboxPublisher;

    public OutboxExecutionLifecyclePublisher(OutboxMessagePublisher outboxPublisher)
    {
        _outboxPublisher = outboxPublisher;
    }

    public Task PublishStartedAsync(string executionId, string executionAttemptId, CancellationToken ct = default)
    {
        return _outboxPublisher.EnqueueAsync(
            PortalMessageTypes.ExecutionStarted,
            new
            {
                ExecutionId = executionId,
                ExecutionAttemptId = executionAttemptId
            },
            executionId: executionId,
            executionAttemptId: executionAttemptId,
            ct: ct);
    }
}
