using Biason.AutomationAgent.Domain.Models.Connections;

namespace Biason.AutomationAgent.Domain.Contracts;

/// <summary>Persiste o estado da conexão em <c>portal_connections</c> e <c>connection_events</c>.</summary>
public interface IConnectionStateRepository
{
    Task SaveStatusAsync(ConnectionStatus status, CancellationToken ct = default);

    Task<ConnectionStatus?> GetLatestStatusAsync(CancellationToken ct = default);

    Task RecordEventAsync(ConnectionEvent evt, CancellationToken ct = default);

    Task<IReadOnlyList<ConnectionEvent>> GetRecentEventsAsync(int limit = 50, CancellationToken ct = default);
}
