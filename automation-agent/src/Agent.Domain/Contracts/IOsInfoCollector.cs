using Biason.AutomationAgent.Domain.Models;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface IOsInfoCollector
{
    OsInfo Collect();
}
