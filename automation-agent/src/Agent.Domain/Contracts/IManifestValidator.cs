using Biason.AutomationAgent.Domain.Models;

namespace Biason.AutomationAgent.Domain.Contracts;

public interface IManifestValidator
{
    /// <summary>
    /// Parse and validate an automation.yaml manifest file.
    /// </summary>
    Task<ManifestValidationResult> ValidateAsync(string manifestPath, CancellationToken ct = default);

    /// <summary>
    /// Parse and validate manifest content directly (JSON string).
    /// </summary>
    Task<ManifestValidationResult> ValidateContentAsync(string jsonContent, CancellationToken ct = default);
}

public sealed class ManifestValidationResult
{
    public bool IsValid { get; init; }
    public AutomationManifest? Manifest { get; init; }
    public IReadOnlyList<string> Errors { get; init; } = Array.Empty<string>();
}
