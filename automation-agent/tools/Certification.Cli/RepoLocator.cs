namespace Biason.AutomationAgent.Certification.Cli;

public static class RepoLocator
{
    /// <summary>
    /// Finds the repository root by walking up from the current directory
    /// looking for scripts/portal.ps1, or trusts CERTIFICATION_REPO_ROOT if
    /// set. Kept independent of where `dotnet run` / the published exe
    /// happens to be invoked from.
    /// </summary>
    private static readonly string Marker = Path.Combine("scripts", "portal.ps1");

    public static string Resolve()
    {
        var overridePath = Environment.GetEnvironmentVariable("CERTIFICATION_REPO_ROOT");
        if (!string.IsNullOrEmpty(overridePath))
        {
            if (!File.Exists(Path.Combine(overridePath, Marker)))
                throw new InvalidOperationException(
                    $"CERTIFICATION_REPO_ROOT={overridePath} does not contain scripts/portal.ps1.");
            return Path.GetFullPath(overridePath);
        }

        var current = new DirectoryInfo(Directory.GetCurrentDirectory());
        for (var depth = 0; depth < 8 && current is not null; depth++)
        {
            if (File.Exists(Path.Combine(current.FullName, Marker)))
                return current.FullName;
            current = current.Parent;
        }

        throw new InvalidOperationException(
            "Could not locate the repository root (scripts/portal.ps1 not found in any parent directory). " +
            "Run this from inside the repo, or set CERTIFICATION_REPO_ROOT.");
    }
}
