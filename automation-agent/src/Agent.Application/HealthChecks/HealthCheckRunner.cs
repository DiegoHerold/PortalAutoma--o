using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models;
using Microsoft.Extensions.Logging;

namespace Biason.AutomationAgent.Application.HealthChecks;

public sealed class HealthCheckRunner
{
    private readonly IDatabaseManager _dbManager;
    private readonly IDirectoryResolver _dirs;
    private readonly IClock _clock;
    private readonly ILogger<HealthCheckRunner> _logger;

    public HealthCheckRunner(
        IDatabaseManager dbManager,
        IDirectoryResolver dirs,
        IClock clock,
        ILogger<HealthCheckRunner> logger)
    {
        _dbManager = dbManager;
        _dirs = dirs;
        _clock = clock;
        _logger = logger;
    }

    public async Task<IReadOnlyList<HealthCheckResult>> RunAllAsync(CancellationToken ct = default)
    {
        var results = new List<HealthCheckResult>
        {
            CheckProcess(),
            await CheckDatabaseAsync(ct),
            CheckStorage(),
            CheckConfiguration()
        };

        foreach (var r in results)
        {
            if (r.Status != HealthStatus.Healthy)
                _logger.LogWarning("Health check {Component}: {Status} - {Message}", r.Component, r.Status, r.Message);
        }

        return results;
    }

    public HealthStatus GetOverallStatus(IReadOnlyList<HealthCheckResult> results)
    {
        if (results.Any(r => r.Status == HealthStatus.Unhealthy))
            return HealthStatus.Unhealthy;
        if (results.Any(r => r.Status == HealthStatus.Degraded))
            return HealthStatus.Degraded;
        return HealthStatus.Healthy;
    }

    private HealthCheckResult CheckProcess()
    {
        return new HealthCheckResult
        {
            Component = "process",
            Status = HealthStatus.Healthy,
            Message = "Process is running",
            CheckedAtUtc = _clock.UtcNow
        };
    }

    private async Task<HealthCheckResult> CheckDatabaseAsync(CancellationToken ct)
    {
        try
        {
            var ok = await _dbManager.VerifyIntegrityAsync(ct);
            return new HealthCheckResult
            {
                Component = "database",
                Status = ok ? HealthStatus.Healthy : HealthStatus.Unhealthy,
                Message = ok ? "Database integrity OK" : "Database integrity check failed",
                CheckedAtUtc = _clock.UtcNow
            };
        }
        catch (Exception ex)
        {
            return new HealthCheckResult
            {
                Component = "database",
                Status = HealthStatus.Unhealthy,
                Message = $"Database check error: {ex.Message}",
                CheckedAtUtc = _clock.UtcNow
            };
        }
    }

    private HealthCheckResult CheckStorage()
    {
        try
        {
            var root = Path.GetPathRoot(_dirs.RootPath) ?? "C:\\";
            var drive = new DriveInfo(root);
            var freeMb = drive.AvailableFreeSpace / (1024 * 1024);

            if (freeMb < 512)
            {
                return new HealthCheckResult
                {
                    Component = "storage",
                    Status = HealthStatus.Unhealthy,
                    Message = $"Critical disk space: {freeMb}MB free",
                    CheckedAtUtc = _clock.UtcNow
                };
            }

            if (freeMb < 2048)
            {
                return new HealthCheckResult
                {
                    Component = "storage",
                    Status = HealthStatus.Degraded,
                    Message = $"Low disk space: {freeMb}MB free",
                    CheckedAtUtc = _clock.UtcNow
                };
            }

            return new HealthCheckResult
            {
                Component = "storage",
                Status = HealthStatus.Healthy,
                Message = $"Disk space OK: {freeMb}MB free",
                CheckedAtUtc = _clock.UtcNow
            };
        }
        catch (Exception ex)
        {
            return new HealthCheckResult
            {
                Component = "storage",
                Status = HealthStatus.Degraded,
                Message = $"Storage check error: {ex.Message}",
                CheckedAtUtc = _clock.UtcNow
            };
        }
    }

    private HealthCheckResult CheckConfiguration()
    {
        var valid = _dirs.Validate(out var errors);
        return new HealthCheckResult
        {
            Component = "configuration",
            Status = valid ? HealthStatus.Healthy : HealthStatus.Degraded,
            Message = valid ? "Configuration OK" : $"Configuration issues: {string.Join("; ", errors)}",
            CheckedAtUtc = _clock.UtcNow
        };
    }
}
