using Biason.AutomationAgent.Domain.Enums;

namespace Biason.AutomationAgent.Domain.Models;

public sealed class HealthCheckResult
{
    public string Component { get; init; } = default!;
    public HealthStatus Status { get; init; }
    public string? Message { get; init; }
    public DateTime CheckedAtUtc { get; init; }
}
