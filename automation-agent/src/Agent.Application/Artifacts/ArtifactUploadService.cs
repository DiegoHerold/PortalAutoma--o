using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Contracts;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace Biason.AutomationAgent.Application.Artifacts;

public sealed class ArtifactUploadService : BackgroundService
{
    private readonly IArtifactUploadManager _uploadManager;
    private readonly ExecutionOptions _options;
    private readonly ILogger<ArtifactUploadService> _logger;

    public ArtifactUploadService(
        IArtifactUploadManager uploadManager,
        IOptions<ExecutionOptions> options,
        ILogger<ArtifactUploadService> logger)
    {
        _uploadManager = uploadManager;
        _options = options.Value;
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        try
        {
            await _uploadManager.RecoverUploadingAsync(stoppingToken);
        }
        catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
        {
            return;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Artifact upload recovery failed.");
        }

        using var timer = new PeriodicTimer(TimeSpan.FromSeconds(_options.ArtifactUploadPollIntervalSeconds));

        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                await _uploadManager.ProcessDueAsync(stoppingToken);
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
            {
                break;
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Artifact upload cycle failed.");
            }

            try { await timer.WaitForNextTickAsync(stoppingToken); }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested) { break; }
        }
    }
}
