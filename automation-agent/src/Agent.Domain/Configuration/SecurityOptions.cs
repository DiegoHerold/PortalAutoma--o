namespace Biason.AutomationAgent.Domain.Configuration;

public sealed class SecurityOptions
{
    public const string Section = "Security";

    /// <summary>Require SHA-256 verification for all downloads.</summary>
    public bool RequireHashVerification { get; init; } = true;

    /// <summary>Require package signature in production.</summary>
    public bool RequirePackageSignature { get; init; } = false;

    /// <summary>Block path traversal in archives (../ in zip entries).</summary>
    public bool BlockPathTraversal { get; init; } = true;

    /// <summary>Allowed executable extensions in packages.</summary>
    public IReadOnlyList<string> AllowedExecutableExtensions { get; init; } = new[] { ".py", ".ps1", ".exe" };
}
