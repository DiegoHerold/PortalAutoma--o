using Biason.AutomationAgent.Domain.Enums;

namespace Biason.AutomationAgent.Domain.Models.Interactive;

public sealed class ResourceLockRecord
{
    public string LockKey { get; init; } = default!;
    public string OwnerExecutionId { get; init; } = default!;
    public string OwnerAttemptId { get; init; } = default!;
    public int? SessionId { get; init; }
    public DateTime CreatedAtUtc { get; init; }
    public DateTime LeaseExpiresAtUtc { get; set; }
    public DateTime? LastRenewedAtUtc { get; set; }
    public DateTime? ReleasedAtUtc { get; set; }
    public DesktopLockStatus Status { get; set; } = DesktopLockStatus.Reserved;
}
