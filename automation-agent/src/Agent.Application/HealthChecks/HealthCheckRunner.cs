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
    private readonly ICacheManager? _cacheManager;
    private readonly ICapacityManager? _capacityManager;
    private readonly ILogger<HealthCheckRunner> _logger;

    public HealthCheckRunner(
        IDatabaseManager dbManager,
        IDirectoryResolver dirs,
        IClock clock,
        ILogger<HealthCheckRunner> logger,
        ICacheManager? cacheManager = null,
        ICapacityManager? capacityManager = null)
    {
        _dbManager = dbManager;
        _dirs = dirs;
        _clock = clock;
        _cacheManager = cacheManager;
        _capacityManager = capacityManager;
        _logger = logger;
    }

    public async Task<IReadOnlyList<HealthCheckResult>> RunAllAsync(CancellationToken ct = default)
    {
        var results = new List<HealthCheckResult>
        {
            CheckProcess(),
            await CheckDatabaseAsync(ct),
            CheckStorage(),
            CheckConfiguration(),
            CheckRuntimeStore(),
            CheckPackageStore(),
            CheckCapacityManager(),
            CheckExecutionHostAvailability()
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

    private HealthCheckResult CheckRuntimeStore()
    {
        try
        {
            var path = _dirs.RuntimesPath;
            var exists = Directory.Exists(path);
            return new HealthCheckResult
            {
                Component = "runtime_store",
                Status = exists ? HealthStatus.Healthy : HealthStatus.Degraded,
                Message = exists ? "Runtime store directory exists" : "Runtime store directory missing",
                CheckedAtUtc = _clock.UtcNow
            };
        }
        catch (Exception ex)
        {
            return new HealthCheckResult
            {
                Component = "runtime_store",
                Status = HealthStatus.Degraded,
                Message = $"Runtime store check error: {ex.Message}",
                CheckedAtUtc = _clock.UtcNow
            };
        }
    }

    private HealthCheckResult CheckPackageStore()
    {
        try
        {
            var path = _dirs.PackagesPath;
            var exists = Directory.Exists(path);
            return new HealthCheckResult
            {
                Component = "package_store",
                Status = exists ? HealthStatus.Healthy : HealthStatus.Degraded,
                Message = exists ? "Package store directory exists" : "Package store directory missing",
                CheckedAtUtc = _clock.UtcNow
            };
        }
        catch (Exception ex)
        {
            return new HealthCheckResult
            {
                Component = "package_store",
                Status = HealthStatus.Degraded,
                Message = $"Package store check error: {ex.Message}",
                CheckedAtUtc = _clock.UtcNow
            };
        }
    }

    private HealthCheckResult CheckCapacityManager()
    {
        if (_capacityManager is null)
        {
            return new HealthCheckResult
            {
                Component = "capacity_manager",
                Status = HealthStatus.Degraded,
                Message = "Capacity manager not available",
                CheckedAtUtc = _clock.UtcNow
            };
        }

        try
        {
            var snapshot = _capacityManager.GetSnapshot();
            var totalAvailable = snapshot.Pools.Values.Sum(p => p.Available);
            return new HealthCheckResult
            {
                Component = "capacity_manager",
                Status = totalAvailable > 0 ? HealthStatus.Healthy : HealthStatus.Degraded,
                Message = $"Capacity: {totalAvailable} slots available across {snapshot.Pools.Count} pools",
                CheckedAtUtc = _clock.UtcNow
            };
        }
        catch (Exception ex)
        {
            return new HealthCheckResult
            {
                Component = "capacity_manager",
                Status = HealthStatus.Degraded,
                Message = $"Capacity check error: {ex.Message}",
                CheckedAtUtc = _clock.UtcNow
            };
        }
    }

    private HealthCheckResult CheckExecutionHostAvailability()
    {
        try
        {
            var candidates = new[]
            {
                Path.Combine(AppContext.BaseDirectory, "ExecutionHost.exe"),
                Path.Combine(AppContext.BaseDirectory, "..", "Agent.ExecutionHost", "ExecutionHost.exe"),
            };

            var found = candidates.Any(File.Exists);
            return new HealthCheckResult
            {
                Component = "execution_host",
                Status = found ? HealthStatus.Healthy : HealthStatus.Degraded,
                Message = found ? "ExecutionHost.exe available" : "ExecutionHost.exe not found",
                CheckedAtUtc = _clock.UtcNow
            };
        }
        catch (Exception ex)
        {
            return new HealthCheckResult
            {
                Component = "execution_host",
                Status = HealthStatus.Degraded,
                Message = $"ExecutionHost check error: {ex.Message}",
                CheckedAtUtc = _clock.UtcNow
            };
        }
    }
}
