using Biason.AutomationAgent.Domain.Models;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface IMachineProfiler
{
    Task<MachineProfileSnapshot> CaptureProfileAsync(CancellationToken ct = default);
}
