namespace Biason.AutomationAgent.Domain.Contracts;

public interface ICancellationManager
{
    CancellationTokenSource CreateLinked(string executionId, int timeoutSeconds, CancellationToken parent);
    Task RequestCancellationAsync(string executionId, CancellationToken ct = default);
    void Remove(string executionId);
}
