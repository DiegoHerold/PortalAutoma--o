namespace Biason.AutomationAgent.Certification.Cli;

public static class RepoLocator
{
    /// <summary>
    /// Finds the repository root by walking up from the current directory
    /// looking for docker-compose.yml, or trusts CERTIFICATION_REPO_ROOT if
    /// set. Kept independent of where `dotnet run` / the published exe
    /// happens to be invoked from.
    /// </summary>
    public static string Resolve()
    {
        var overridePath = Environment.GetEnvironmentVariable("CERTIFICATION_REPO_ROOT");
        if (!string.IsNullOrEmpty(overridePath))
        {
            if (!File.Exists(Path.Combine(overridePath, "docker-compose.yml")))
                throw new InvalidOperationException(
                    $"CERTIFICATION_REPO_ROOT={overridePath} does not contain docker-compose.yml.");
            return Path.GetFullPath(overridePath);
        }

        var current = new DirectoryInfo(Directory.GetCurrentDirectory());
        for (var depth = 0; depth < 8 && current is not null; depth++)
        {
            if (File.Exists(Path.Combine(current.FullName, "docker-compose.yml")))
                return current.FullName;
            current = current.Parent;
        }

        throw new InvalidOperationException(
            "Could not locate the repository root (docker-compose.yml not found in any parent directory). " +
            "Run this from inside the repo, or set CERTIFICATION_REPO_ROOT.");
    }
}
