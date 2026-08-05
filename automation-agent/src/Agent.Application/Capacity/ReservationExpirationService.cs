using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Contracts;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace Biason.AutomationAgent.Application.Capacity;

/// <summary>
/// Expira reservas TEMPORARY vencidas em um ciclo próprio, independente do
/// boot (Bloco 5.5, seção 11). Sem isso, uma reserva só seria liberada na
/// próxima vez que o Agent reiniciasse — prendendo capacidade indefinidamente
/// entre restarts.
/// </summary>
public sealed class ReservationExpirationService : BackgroundService
{
    private readonly IResourceReservationManager _reservations;
    private readonly ExecutionOptions _options;
    private readonly ILogger<ReservationExpirationService> _logger;

    public ReservationExpirationService(
        IResourceReservationManager reservations,
        IOptions<ExecutionOptions> options,
        ILogger<ReservationExpirationService> logger)
    {
        _reservations = reservations;
        _options = options.Value;
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        using var timer = new PeriodicTimer(TimeSpan.FromSeconds(_options.ReservationExpirationPollIntervalSeconds));

        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                await _reservations.ExpireStaleAsync(stoppingToken);
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
            {
                break;
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Reservation expiration cycle failed.");
            }

            try { await timer.WaitForNextTickAsync(stoppingToken); }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested) { break; }
        }
    }
}
