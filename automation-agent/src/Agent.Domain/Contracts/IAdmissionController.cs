using Biason.AutomationAgent.Domain.Models;
using Biason.AutomationAgent.Domain.Models.Capacity;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface IAdmissionController
{
    /// <summary>Evaluate if an execution can be admitted. Returns decision with reservation if accepted.</summary>
    Task<AdmissionDecision> EvaluateAsync(ExecutionRecord execution, AutomationManifest manifest, CancellationToken ct = default);
}
