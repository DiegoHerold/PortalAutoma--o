using Biason.AutomationAgent.Domain.Models;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface ISessionInfoCollector
{
    SessionInfo Collect();
}
