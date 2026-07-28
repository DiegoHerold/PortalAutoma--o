using Biason.AutomationAgent.Domain.Contracts;

namespace Biason.AutomationAgent.Infrastructure.Clock;

public sealed class SystemClock : IClock
{
    public DateTime UtcNow => DateTime.UtcNow;
}
