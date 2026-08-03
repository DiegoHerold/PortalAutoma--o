using Biason.AutomationAgent.Domain.Contracts;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

namespace Biason.AutomationAgent.Application.Connection;

/// <summary>
/// Ponte entre o ciclo de vida do host (.NET Generic Host) e
/// <see cref="IPortalConnectionManager.RunAsync"/>. Não contém lógica própria — só
/// garante que o laço de conexão inicia com o serviço e é cancelado no shutdown.
/// </summary>
public sealed class PortalConnectionHostedService : BackgroundService
{
    private readonly IPortalConnectionManager _connection;
    private readonly ILogger<PortalConnectionHostedService> _logger;

    public PortalConnectionHostedService(IPortalConnectionManager connection, ILogger<PortalConnectionHostedService> logger)
    {
        _connection = connection;
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        try
        {
            await _connection.RunAsync(stoppingToken);
        }
        catch (OperationCanceledException)
        {
            // encerramento normal do host
        }
        catch (Exception ex)
        {
            // RunAsync não deveria propagar exceções não tratadas (todo caminho de
            // falha é capturado e vira um estado de conexão), mas se algo inesperado
            // escapar, não deve derrubar o processo — só logamos.
            _logger.LogError(ex, "PortalConnectionManager.RunAsync encerrou por exceção não tratada.");
        }
    }
}
