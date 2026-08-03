using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Sessions;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface ISessionRunnerRepository
{
    Task UpsertAsync(SessionRunnerRecord runner, CancellationToken ct = default);
    Task<SessionRunnerRecord?> GetAsync(string instanceId, CancellationToken ct = default);
    Task<IReadOnlyList<SessionRunnerRecord>> GetAllAsync(CancellationToken ct = default);
    Task<IReadOnlyList<SessionRunnerRecord>> GetConnectedAsync(CancellationToken ct = default);
    Task UpdateHeartbeatAsync(string instanceId, DateTime heartbeatAtUtc, DesktopState desktop, CancellationToken ct = default);
    Task MarkDisconnectedAsync(string instanceId, DateTime disconnectedAtUtc, string reason, CancellationToken ct = default);
    Task UpdateTokenFingerprintAsync(string instanceId, string fingerprint, DateTime expiresAtUtc, CancellationToken ct = default);
    Task UpdateStateAsync(string instanceId, SessionRunnerConnectionState state, CancellationToken ct = default);
}
