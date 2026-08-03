using Biason.AutomationAgent.Domain.Models.Sessions;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface ISessionRunnerRegistry
{
    Task RegisterAsync(SessionRunnerRecord runner, CancellationToken ct = default);
    Task RecordHeartbeatAsync(string instanceId, DateTime heartbeatAtUtc, DesktopState desktop, CancellationToken ct = default);
    Task MarkDisconnectedAsync(string instanceId, string reason, CancellationToken ct = default);
    Task MarkTimedOutAsync(DateTime nowUtc, CancellationToken ct = default);
    Task<IReadOnlyList<SessionRunnerRecord>> GetSnapshotAsync(CancellationToken ct = default);
    bool TryValidateSessionToken(string token, string instanceId, int sessionId, int processId, DateTime nowUtc);
    string IssueSessionToken(string instanceId, int sessionId, int processId, DateTime expiresAtUtc, out string fingerprint);
    bool TryGetSessionToken(string instanceId, out string token);
    void InvalidateSessionToken(string instanceId);
}
