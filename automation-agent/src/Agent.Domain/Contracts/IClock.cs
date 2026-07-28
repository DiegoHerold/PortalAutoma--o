namespace Biason.AutomationAgent.Domain.Contracts;

public interface IClock
{
    DateTime UtcNow { get; }
}
