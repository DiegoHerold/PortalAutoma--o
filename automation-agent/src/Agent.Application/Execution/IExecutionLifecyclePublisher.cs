namespace Biason.AutomationAgent.Application.Execution;

public interface IExecutionLifecyclePublisher
{
    Task PublishStartedAsync(string executionId, string executionAttemptId, CancellationToken ct = default);
}
