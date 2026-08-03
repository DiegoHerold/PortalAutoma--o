using Biason.AutomationAgent.Domain.Models.Sessions;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface IWindowsSessionDiscovery
{
    Task<IReadOnlyList<WindowsSession>> DiscoverAsync(CancellationToken ct = default);
    int? GetActiveConsoleSessionId();
}
