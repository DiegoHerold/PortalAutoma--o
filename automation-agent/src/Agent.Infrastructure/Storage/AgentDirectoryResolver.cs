using Biason.AutomationAgent.Domain.Contracts;
using Microsoft.Extensions.Logging;

namespace Biason.AutomationAgent.Infrastructure.Storage;

public sealed class AgentDirectoryResolver : IDirectoryResolver
{
    private const string DefaultRootPath = @"C:\ProgramData\BiasonAutomationAgent";
    private const string EnvVarName = "AUTOMATION_AGENT_DATA_DIR";

    public string RootPath { get; }
    public string ConfigPath => Path.Combine(RootPath, "config");
    public string DatabasePath => Path.Combine(RootPath, "database");
    public string StorePath => Path.Combine(RootPath, "store");
    public string RuntimesPath => Path.Combine(StorePath, "runtimes");
    public string PackagesPath => Path.Combine(StorePath, "packages");
    public string DownloadsPath => Path.Combine(RootPath, "downloads");
    public string StagingPath => Path.Combine(RootPath, "staging");
    public string ExecutionsPath => Path.Combine(RootPath, "executions");
    public string ArtifactsPath => Path.Combine(RootPath, "artifacts");
    public string SpoolPath => Path.Combine(RootPath, "spool");
    public string DiagnosticsPath => Path.Combine(RootPath, "diagnostics");
    public string LogsPath => Path.Combine(RootPath, "logs");
    public string DatabaseFilePath => Path.Combine(DatabasePath, "agent.db");

    private readonly ILogger<AgentDirectoryResolver> _logger;

    public AgentDirectoryResolver(ILogger<AgentDirectoryResolver> logger, string? overridePath = null)
    {
        _logger = logger;

        var envPath = Environment.GetEnvironmentVariable(EnvVarName);
        RootPath = !string.IsNullOrWhiteSpace(overridePath)
            ? overridePath
            : !string.IsNullOrWhiteSpace(envPath)
                ? envPath
                : DefaultRootPath;

        if (!string.IsNullOrWhiteSpace(envPath) && string.IsNullOrWhiteSpace(overridePath))
            _logger.LogInformation("Using data directory from environment variable {EnvVar}: {Path}", EnvVarName, envPath);
    }

    public void EnsureDirectoriesExist()
    {
        var dirs = new[]
        {
            ConfigPath, DatabasePath, StorePath, RuntimesPath, PackagesPath,
            DownloadsPath, StagingPath, ExecutionsPath, ArtifactsPath,
            SpoolPath, DiagnosticsPath, LogsPath
        };

        foreach (var dir in dirs)
        {
            if (!Directory.Exists(dir))
            {
                Directory.CreateDirectory(dir);
                _logger.LogInformation("Created directory: {Path}", dir);
            }
        }
    }

    public bool Validate(out IReadOnlyList<string> errors)
    {
        var errs = new List<string>();

        if (string.IsNullOrWhiteSpace(RootPath))
            errs.Add("Root path is empty.");

        if (RootPath.Length > 200)
            errs.Add($"Root path is too long ({RootPath.Length} characters).");

        try
        {
            var fullPath = Path.GetFullPath(RootPath);
            if (fullPath != RootPath.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar))
            {
                // Path normalization changed it, which is fine but log it
                _logger.LogDebug("Root path normalized from {Original} to {Normalized}", RootPath, fullPath);
            }
        }
        catch (Exception ex)
        {
            errs.Add($"Root path is invalid: {ex.Message}");
        }

        errors = errs;
        return errs.Count == 0;
    }
}
