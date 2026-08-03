using Biason.AutomationAgent.Domain.Models.Sessions;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface IDesktopStateReader
{
    DesktopState ReadCurrent();
}
