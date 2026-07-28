using Biason.AutomationAgent.Domain.Models;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface IResourceMonitor
{
    Task<ResourceSample> CaptureCurrentAsync(CancellationToken ct = default);
    Task<ResourceMetrics> GetMetricsAsync(CancellationToken ct = default);
}
