using Biason.AutomationAgent.Domain.Enums;

namespace Biason.AutomationAgent.Domain.Models.Sessions;

public sealed class SessionRunnerRecord
{
    public string InstanceId { get; init; } = default!;
    public int SessionId { get; init; }
    public string? UserName { get; init; }
    public string? DomainName { get; init; }
    public SessionType SessionType { get; init; } = SessionType.Unknown;
    public int? ProcessId { get; init; }
    public string? Version { get; init; }
    public DesktopState Desktop { get; init; } = DesktopState.Unknown;
    public SessionRunnerConnectionState State { get; set; } = SessionRunnerConnectionState.Connecting;
    public DateTime RegisteredAtUtc { get; init; }
    public DateTime? LastHeartbeatAtUtc { get; set; }
    public DateTime? DisconnectedAtUtc { get; set; }
    public string? SessionTokenFingerprint { get; set; }
    public DateTime? SessionTokenExpiresAtUtc { get; set; }
}
