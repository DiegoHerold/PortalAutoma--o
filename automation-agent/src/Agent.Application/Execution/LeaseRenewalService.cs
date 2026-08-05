using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Contracts;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace Biason.AutomationAgent.Application.Execution;

/// <summary>
/// Varre leases de execução em um ciclo próprio, independente do boot
/// (Bloco 5.5, seção 19 — mesmo raciocínio de
/// <c>ReservationExpirationService</c> para reservas): sem isso, um lease
/// perto de expirar só seria renovado/perdido na próxima vez que algo
/// disparasse a varredura manualmente.
/// </summary>
public sealed class LeaseRenewalService : BackgroundService
{
    private readonly IExecutionLeaseManager _leaseManager;
    private readonly ExecutionOptions _options;
    private readonly ILogger<LeaseRenewalService> _logger;

    public LeaseRenewalService(
        IExecutionLeaseManager leaseManager,
        IOptions<ExecutionOptions> options,
        ILogger<LeaseRenewalService> logger)
    {
        _leaseManager = leaseManager;
        _options = options.Value;
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        using var timer = new PeriodicTimer(TimeSpan.FromSeconds(_options.LeaseRenewalPollIntervalSeconds));

        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                await _leaseManager.RenewDueLeasesAsync(stoppingToken);
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
            {
                break;
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Lease renewal cycle failed.");
            }

            try { await timer.WaitForNextTickAsync(stoppingToken); }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested) { break; }
        }
    }
}
