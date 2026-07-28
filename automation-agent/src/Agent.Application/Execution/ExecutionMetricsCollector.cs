using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Models.Execution;
using Microsoft.Extensions.Logging;

namespace Biason.AutomationAgent.Application.Execution;

/// <summary>
/// Collects and aggregates per-execution metrics from the workspace metrics file
/// and process monitoring data.
/// </summary>
public sealed class ExecutionMetricsCollector
{
    private readonly IClock _clock;
    private readonly ILogger<ExecutionMetricsCollector> _logger;

    public ExecutionMetricsCollector(IClock clock, ILogger<ExecutionMetricsCollector> logger)
    {
        _clock = clock;
        _logger = logger;
    }

    /// <summary>
    /// Read metrics from the workspace output and update the attempt record.
    /// </summary>
    public void UpdateAttemptMetrics(ExecutionAttempt attempt, string workspacePath)
    {
        try
        {
            var metricsPath = Path.Combine(workspacePath, "output", "metrics.json");
            if (!File.Exists(metricsPath)) return;

            var json = File.ReadAllText(metricsPath);
            using var doc = System.Text.Json.JsonDocument.Parse(json);
            var root = doc.RootElement;

            if (root.TryGetProperty("peak_memory_mb", out var mem))
                attempt.PeakMemoryMb = mem.GetInt64();

            if (root.TryGetProperty("cpu_time_seconds", out var cpu))
                attempt.CpuTimeSeconds = cpu.GetDouble();
        }
        catch (Exception ex)
        {
            _logger.LogDebug(ex, "Could not read metrics for attempt {AttemptId}", attempt.AttemptId);
        }
    }

    /// <summary>
    /// Calculate workspace size in MB.
    /// </summary>
    public long GetWorkspaceSizeMb(string workspacePath)
    {
        try
        {
            if (!Directory.Exists(workspacePath)) return 0;
            return new DirectoryInfo(workspacePath)
                .EnumerateFiles("*", SearchOption.AllDirectories)
                .Sum(f => f.Length) / (1024 * 1024);
        }
        catch { return 0; }
    }
}
