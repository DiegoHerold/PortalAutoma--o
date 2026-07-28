namespace Biason.AutomationAgent.Domain.Contracts;

public interface IDirectoryResolver
{
    string RootPath { get; }
    string ConfigPath { get; }
    string DatabasePath { get; }
    string StorePath { get; }
    string RuntimesPath { get; }
    string PackagesPath { get; }
    string DownloadsPath { get; }
    string StagingPath { get; }
    string ExecutionsPath { get; }
    string ArtifactsPath { get; }
    string SpoolPath { get; }
    string DiagnosticsPath { get; }
    string LogsPath { get; }
    string DatabaseFilePath { get; }
    void EnsureDirectoriesExist();
    bool Validate(out IReadOnlyList<string> errors);
}
