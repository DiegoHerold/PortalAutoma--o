using System.Diagnostics;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Models;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace Biason.AutomationAgent.Application.Services;

public sealed class ResourceMonitorService : BackgroundService, IResourceMonitor
{
    private readonly ICpuUsageProvider _cpuUsageProvider;
    private readonly IMemoryInfoCollector _memoryCollector;
    private readonly IDiskInfoCollector _diskCollector;
    private readonly ISessionInfoCollector _sessionCollector;
    private readonly IResourceSampleRepository _repository;
    private readonly IDatabaseManager _dbManager;
    private readonly IDirectoryResolver _dirs;
    private readonly IClock _clock;
    private readonly MonitoringOptions _options;
    private readonly ILogger<ResourceMonitorService> _logger;
    private ResourceSample? _lastSample;

    public ResourceMonitorService(
        ICpuUsageProvider cpuUsageProvider,
        IMemoryInfoCollector memoryCollector,
        IDiskInfoCollector diskCollector,
        ISessionInfoCollector sessionCollector,
        IResourceSampleRepository repository,
        IDatabaseManager dbManager,
        IDirectoryResolver dirs,
        IClock clock,
        IOptions<MonitoringOptions> options,
        ILogger<ResourceMonitorService> logger)
    {
        _cpuUsageProvider = cpuUsageProvider;
        _memoryCollector = memoryCollector;
        _diskCollector = diskCollector;
        _sessionCollector = sessionCollector;
        _repository = repository;
        _dbManager = dbManager;
        _dirs = dirs;
        _clock = clock;
        _options = options.Value;
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        _logger.LogInformation("Resource monitor started (interval={Interval}s, retention={Retention}min)",
            _options.SampleIntervalSeconds, _options.HistoryRetentionMinutes);

        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                var sample = await CaptureCurrentAsync(stoppingToken);
                await _repository.SaveAsync(sample, stoppingToken);
                _lastSample = sample;

                // Purge old samples periodically
                var cutoff = _clock.UtcNow.AddMinutes(-_options.HistoryRetentionMinutes);
                await _repository.PurgeOlderThanAsync(cutoff, stoppingToken);
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
            {
                break;
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Error during resource monitoring cycle");
            }

            try
            {
                await Task.Delay(TimeSpan.FromSeconds(_options.SampleIntervalSeconds), stoppingToken);
            }
            catch (OperationCanceledException)
            {
                break;
            }
        }

        _logger.LogInformation("Resource monitor stopped");
    }

    public Task<ResourceSample> CaptureCurrentAsync(CancellationToken ct = default)
    {
        var now = _clock.UtcNow;
        var memory = _memoryCollector.Collect();
        var disk = _diskCollector.Collect();
        var session = _sessionCollector.Collect();

        long agentMemoryMb = 0;
        int processCount = 0;
        try
        {
            using var proc = Process.GetCurrentProcess();
            agentMemoryMb = proc.WorkingSet64 / (1024 * 1024);
            processCount = Process.GetProcesses().Length;
        }
        catch { /* ignore */ }

        var sample = new ResourceSample
        {
            SampledAtUtc = now,
            CpuUsagePercent = _cpuUsageProvider.GetCpuUsagePercent(),
            MemoryTotalMb = memory.TotalMb,
            MemoryAvailableMb = memory.AvailableMb,
            MemoryUsedMb = memory.UsedMb,
            MemoryUsagePercent = memory.UsagePercent,
            DiskTotalMb = disk.TotalMb,
            DiskFreeMb = disk.FreeMb,
            DiskUsagePercent = disk.UsagePercent,
            AgentMemoryMb = agentMemoryMb,
            ProcessCount = processCount,
            UptimeSeconds = Environment.TickCount64 / 1000,
            DatabaseSizeKb = _dbManager.GetDatabaseSizeKb(),
            LogsSizeKb = GetDirectorySizeKb(_dirs.LogsPath),
            SpoolSizeKb = GetDirectorySizeKb(_dirs.SpoolPath),
            CacheSizeKb = GetDirectorySizeKb(_dirs.StorePath),
            SessionStatus = session.Status.ToString().ToLowerInvariant()
        };

        return Task.FromResult(sample);
    }

    public async Task<ResourceMetrics> GetMetricsAsync(CancellationToken ct = default)
    {
        var recent = await _repository.GetRecentAsync(_options.HistoryRetentionMinutes, ct);
        var latest = _lastSample ?? await _repository.GetLatestAsync(ct);

        if (recent.Count == 0)
            return new ResourceMetrics { Current = latest, SampleCount = 0 };

        return new ResourceMetrics
        {
            Current = latest,
            CpuAveragePercent = recent.Average(s => s.CpuUsagePercent),
            CpuMaxPercent = recent.Max(s => s.CpuUsagePercent),
            MemoryAveragePercent = recent.Average(s => s.MemoryUsagePercent),
            MemoryMaxPercent = recent.Max(s => s.MemoryUsagePercent),
            DiskAveragePercent = recent.Average(s => s.DiskUsagePercent),
            SampleCount = recent.Count,
            OldestSampleUtc = recent.Min(s => s.SampledAtUtc),
            NewestSampleUtc = recent.Max(s => s.SampledAtUtc)
        };
    }

    private static long GetDirectorySizeKb(string path)
    {
        try
        {
            if (!Directory.Exists(path)) return 0;
            return new DirectoryInfo(path)
                .EnumerateFiles("*", SearchOption.AllDirectories)
                .Sum(f => f.Length) / 1024;
        }
        catch
        {
            return 0;
        }
    }
}
