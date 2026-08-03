namespace Biason.AutomationAgent.Domain.Models.Sessions;

public sealed class SessionRunnerConnectionRecord
{
    public long Id { get; init; }
    public string SessionRunnerInstanceId { get; init; } = default!;
    public int SessionId { get; init; }
    public DateTime ConnectedAtUtc { get; init; }
    public DateTime? AuthenticatedAtUtc { get; set; }
    public DateTime? DisconnectedAtUtc { get; set; }
    public string? DisconnectReason { get; set; }
    public int? RemoteProcessId { get; init; }
    public string? ProtocolVersion { get; init; }
    public string Status { get; set; } = "connected";
}
