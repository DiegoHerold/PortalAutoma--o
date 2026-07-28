using Biason.AutomationAgent.Domain.Models;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface IMemoryInfoCollector
{
    MemoryInfo Collect();
    double GetCurrentUsagePercent();
}
