namespace Biason.AutomationAgent.Domain.Enums;

public enum ApplicationProcessPolicy
{
    NewInstance,
    AttachOwned,
    RejectIfConflicting,
    Reject,
    Attach,
    Reuse
}
