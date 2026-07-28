using Biason.AutomationAgent.Domain.Contracts;
using Microsoft.Extensions.Logging;

namespace Biason.AutomationAgent.Application.Execution;

public sealed class WorkspaceManager : IWorkspaceManager
{
    private readonly IDirectoryResolver _dirs;
    private readonly ILogger<WorkspaceManager> _logger;

    public WorkspaceManager(IDirectoryResolver dirs, ILogger<WorkspaceManager> logger)
    {
        _dirs = dirs;
        _logger = logger;
    }

    public string CreateWorkspace(string executionId, string attemptId)
    {
        var path = Path.Combine(_dirs.ExecutionsPath, executionId, attemptId);
        Directory.CreateDirectory(path);

        // Create standard subdirectories
        Directory.CreateDirectory(Path.Combine(path, "input"));
        Directory.CreateDirectory(Path.Combine(path, "output"));
        Directory.CreateDirectory(Path.Combine(path, "logs"));
        Directory.CreateDirectory(Path.Combine(path, "temp"));

        _logger.LogInformation("Created workspace: {Path}", path);
        return path;
    }

    public Task CleanupAsync(string workspacePath, CancellationToken ct = default)
    {
        try
        {
            if (Directory.Exists(workspacePath))
            {
                Directory.Delete(workspacePath, recursive: true);
                _logger.LogInformation("Cleaned up workspace: {Path}", workspacePath);
            }
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to cleanup workspace: {Path}", workspacePath);
        }
        return Task.CompletedTask;
    }

    public async Task CleanupStaleAsync(CancellationToken ct = default)
    {
        if (!Directory.Exists(_dirs.ExecutionsPath)) return;

        var execDirs = Directory.GetDirectories(_dirs.ExecutionsPath);
        int cleaned = 0;

        foreach (var dir in execDirs)
        {
            ct.ThrowIfCancellationRequested();

            // If the directory is older than 24 hours and has no lock file, clean it
            var dirInfo = new DirectoryInfo(dir);
            if (dirInfo.LastWriteTimeUtc < DateTime.UtcNow.AddHours(-24))
            {
                var lockFile = Path.Combine(dir, ".lock");
                if (!File.Exists(lockFile))
                {
                    try
                    {
                        Directory.Delete(dir, recursive: true);
                        cleaned++;
                    }
                    catch (Exception ex)
                    {
                        _logger.LogDebug(ex, "Failed to cleanup stale workspace: {Path}", dir);
                    }
                }
            }
        }

        if (cleaned > 0)
            _logger.LogInformation("Cleaned up {Count} stale workspaces", cleaned);
    }
}
