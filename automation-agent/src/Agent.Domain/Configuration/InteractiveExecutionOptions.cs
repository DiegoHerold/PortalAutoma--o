using System.ComponentModel.DataAnnotations;

namespace Biason.AutomationAgent.Domain.Configuration;

public sealed class InteractiveExecutionOptions
{
    public const string Section = "InteractiveExecution";

    [Range(0, 3600)]
    public int SessionLockGraceSeconds { get; init; } = 60;

    public string OnSessionLocked { get; init; } = "wait_then_cancel";

    public string OnRdpDisconnected { get; init; } = "wait_then_cancel";

    public string ExcelExistingProcessPolicy { get; init; } = "new_instance";

    public string DominioExistingProcessPolicy { get; init; } = "reject";
}
