using Biason.AutomationAgent.Domain.Contracts;
using Microsoft.Extensions.Logging;

namespace Biason.AutomationAgent.Application.Execution;

public sealed class CancellationManager : ICancellationManager
{
    private readonly Dictionary<string, CancellationTokenSource> _sources = new();
    private readonly object _lock = new();
    private readonly ILogger<CancellationManager> _logger;

    public CancellationManager(ILogger<CancellationManager> logger) => _logger = logger;

    public CancellationTokenSource CreateLinked(string executionId, int timeoutSeconds, CancellationToken parent)
    {
        var cts = CancellationTokenSource.CreateLinkedTokenSource(parent);
        cts.CancelAfter(TimeSpan.FromSeconds(timeoutSeconds));

        lock (_lock) { _sources[executionId] = cts; }
        _logger.LogDebug("Created cancellation source for {ExecutionId} with timeout {Timeout}s", executionId, timeoutSeconds);
        return cts;
    }

    public Task RequestCancellationAsync(string executionId, CancellationToken ct = default)
    {
        lock (_lock)
        {
            if (_sources.TryGetValue(executionId, out var cts))
            {
                cts.Cancel();
                _logger.LogInformation("Cancellation requested for execution {ExecutionId}", executionId);
            }
            else
            {
                _logger.LogWarning("No cancellation source found for execution {ExecutionId}", executionId);
            }
        }
        return Task.CompletedTask;
    }

    public void Remove(string executionId)
    {
        lock (_lock)
        {
            if (_sources.Remove(executionId, out var cts))
            {
                cts.Dispose();
            }
        }
    }
}
