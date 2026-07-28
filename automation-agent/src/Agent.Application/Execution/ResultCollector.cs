using System.Security.Cryptography;
using System.Text.Json;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Models.Execution;
using Microsoft.Extensions.Logging;

namespace Biason.AutomationAgent.Application.Execution;

public sealed class ResultCollector : IResultCollector
{
    private readonly IClock _clock;
    private readonly ILogger<ResultCollector> _logger;

    public ResultCollector(IClock clock, ILogger<ResultCollector> logger)
    {
        _clock = clock;
        _logger = logger;
    }

    public async Task<ExecutionResult> CollectAsync(
        string executionId,
        string attemptId,
        string workspacePath,
        int? exitCode,
        CancellationToken ct = default)
    {
        var outputJson = await ReadOutputAsync(workspacePath, ct);
        var errorOutput = await ReadErrorAsync(workspacePath, ct);
        var artifacts = await CollectArtifactsAsync(workspacePath, ct);
        var metrics = ReadMetrics(workspacePath);

        var result = new ExecutionResult
        {
            ExecutionId = executionId,
            AttemptId = attemptId,
            Success = exitCode == 0,
            ExitCode = exitCode,
            OutputJson = outputJson,
            ErrorOutput = errorOutput,
            DurationMs = metrics.durationMs,
            PeakMemoryMb = metrics.peakMemoryMb,
            CpuTimeSeconds = metrics.cpuTimeSeconds,
            Artifacts = artifacts,
            CompletedAtUtc = _clock.UtcNow
        };

        _logger.LogInformation(
            "Collected result for execution {ExecutionId}/{AttemptId}: success={Success}, exitCode={ExitCode}, artifacts={ArtifactCount}",
            executionId, attemptId, result.Success, exitCode, artifacts.Count);

        return result;
    }

    private static async Task<string?> ReadOutputAsync(string workspacePath, CancellationToken ct)
    {
        // Check for output.json in the output directory
        var outputPath = Path.Combine(workspacePath, "output", "output.json");
        if (!File.Exists(outputPath)) return null;

        try
        {
            var content = await File.ReadAllTextAsync(outputPath, ct);
            // Validate it's valid JSON
            JsonDocument.Parse(content).Dispose();
            return content;
        }
        catch (JsonException)
        {
            // Return raw content if not valid JSON
            return await File.ReadAllTextAsync(outputPath, ct);
        }
        catch
        {
            return null;
        }
    }

    private static async Task<string?> ReadErrorAsync(string workspacePath, CancellationToken ct)
    {
        var errorPath = Path.Combine(workspacePath, "logs", "stderr.log");
        if (!File.Exists(errorPath)) return null;

        try
        {
            var content = await File.ReadAllTextAsync(errorPath, ct);
            if (string.IsNullOrWhiteSpace(content)) return null;

            // Truncate excessive error output
            const int maxErrorLength = 32 * 1024;
            return content.Length > maxErrorLength
                ? content[..maxErrorLength] + "\n... [truncated]"
                : content;
        }
        catch
        {
            return null;
        }
    }

    private async Task<IReadOnlyList<ExecutionArtifactRef>> CollectArtifactsAsync(
        string workspacePath, CancellationToken ct)
    {
        var artifactsDir = Path.Combine(workspacePath, "artifacts");
        if (!Directory.Exists(artifactsDir)) return Array.Empty<ExecutionArtifactRef>();

        var artifacts = new List<ExecutionArtifactRef>();

        try
        {
            foreach (var file in Directory.EnumerateFiles(artifactsDir, "*", SearchOption.AllDirectories))
            {
                ct.ThrowIfCancellationRequested();

                var info = new FileInfo(file);
                if (!info.Exists) continue;

                var sha256 = await ComputeSha256Async(file, ct);
                var relativePath = Path.GetRelativePath(artifactsDir, file);

                artifacts.Add(new ExecutionArtifactRef
                {
                    ArtifactId = $"art_{Guid.NewGuid():N}",
                    Name = relativePath,
                    ContentType = InferContentType(info.Extension),
                    SizeBytes = info.Length,
                    Sha256 = sha256,
                    LocalPath = file
                });
            }
        }
        catch (OperationCanceledException) { throw; }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Error collecting artifacts from {ArtifactsDir}", artifactsDir);
        }

        return artifacts;
    }

    private static async Task<string> ComputeSha256Async(string filePath, CancellationToken ct)
    {
        using var stream = File.OpenRead(filePath);
        var hash = await SHA256.HashDataAsync(stream, ct);
        return Convert.ToHexString(hash).ToLowerInvariant();
    }

    private static (long? durationMs, long? peakMemoryMb, double? cpuTimeSeconds) ReadMetrics(string workspacePath)
    {
        var metricsPath = Path.Combine(workspacePath, "output", "metrics.json");
        if (!File.Exists(metricsPath)) return (null, null, null);

        try
        {
            var json = File.ReadAllText(metricsPath);
            using var doc = JsonDocument.Parse(json);
            var root = doc.RootElement;

            long? durationMs = root.TryGetProperty("duration_ms", out var d) ? d.GetInt64() : null;
            long? peakMem = root.TryGetProperty("peak_memory_mb", out var m) ? m.GetInt64() : null;
            double? cpuTime = root.TryGetProperty("cpu_time_seconds", out var c) ? c.GetDouble() : null;

            return (durationMs, peakMem, cpuTime);
        }
        catch
        {
            return (null, null, null);
        }
    }

    private static string InferContentType(string extension) => extension.ToLowerInvariant() switch
    {
        ".json" => "application/json",
        ".xml" => "application/xml",
        ".txt" => "text/plain",
        ".csv" => "text/csv",
        ".html" => "text/html",
        ".pdf" => "application/pdf",
        ".png" => "image/png",
        ".jpg" or ".jpeg" => "image/jpeg",
        ".zip" => "application/zip",
        ".xlsx" => "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".docx" => "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        _ => "application/octet-stream"
    };
}
