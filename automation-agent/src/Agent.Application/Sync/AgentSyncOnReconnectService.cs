using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

namespace Biason.AutomationAgent.Application.Sync;

public sealed class AgentSyncOnReconnectService : IHostedService
{
    private readonly IPortalConnectionManager _connection;
    private readonly IAgentSyncService _syncService;
    private readonly ILogger<AgentSyncOnReconnectService> _logger;

    public AgentSyncOnReconnectService(
        IPortalConnectionManager connection,
        IAgentSyncService syncService,
        ILogger<AgentSyncOnReconnectService> logger)
    {
        _connection = connection;
        _syncService = syncService;
        _logger = logger;
    }

    public Task StartAsync(CancellationToken cancellationToken)
    {
        _connection.StateChanged += OnStateChangedAsync;
        return Task.CompletedTask;
    }

    public Task StopAsync(CancellationToken cancellationToken)
    {
        _connection.StateChanged -= OnStateChangedAsync;
        return Task.CompletedTask;
    }

    private async Task OnStateChangedAsync(ConnectionState from, ConnectionState to)
    {
        if (to != ConnectionState.Connected)
            return;

        try
        {
            await _syncService.PublishSyncStateAsync(from == ConnectionState.Reconnecting ? "reconnected" : "connected");
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to publish automatic sync after Portal connection state changed {From}->{To}.", from, to);
        }
    }
}
