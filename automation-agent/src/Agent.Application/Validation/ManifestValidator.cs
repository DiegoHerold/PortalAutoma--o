using System.Text.Json;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models;
using Microsoft.Extensions.Logging;

namespace Biason.AutomationAgent.Application.Validation;

public sealed class ManifestValidator : IManifestValidator
{
    private static readonly HashSet<string> ValidEntrypointTypes = new(StringComparer.OrdinalIgnoreCase)
    {
        "python_function", "python_module", "powershell_script", "executable", "browser_playwright"
    };

    private static readonly HashSet<string> ValidRuntimeIds = new(StringComparer.OrdinalIgnoreCase)
    {
        "python-embedded", "powershell", "executable", "playwright-browser"
    };

    private readonly ILogger<ManifestValidator> _logger;

    public ManifestValidator(ILogger<ManifestValidator> logger) => _logger = logger;

    public async Task<ManifestValidationResult> ValidateAsync(string manifestPath, CancellationToken ct = default)
    {
        if (!File.Exists(manifestPath))
        {
            return new ManifestValidationResult
            {
                IsValid = false,
                Errors = new[] { $"Manifest file not found: {manifestPath}" }
            };
        }

        string content;
        try
        {
            content = await File.ReadAllTextAsync(manifestPath, ct);
        }
        catch (Exception ex)
        {
            return new ManifestValidationResult
            {
                IsValid = false,
                Errors = new[] { $"Failed to read manifest: {ex.Message}" }
            };
        }

        return await ValidateContentAsync(content, ct);
    }

    public Task<ManifestValidationResult> ValidateContentAsync(string jsonContent, CancellationToken ct = default)
    {
        var errors = new List<string>();

        ManifestRaw? raw;
        try
        {
            raw = JsonSerializer.Deserialize<ManifestRaw>(jsonContent, new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true,
                PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower
            });
        }
        catch (JsonException ex)
        {
            return Task.FromResult(new ManifestValidationResult
            {
                IsValid = false,
                Errors = new[] { $"Invalid manifest JSON: {ex.Message}" }
            });
        }

        if (raw is null)
        {
            return Task.FromResult(new ManifestValidationResult { IsValid = false, Errors = new[] { "Manifest parsed as null" } });
        }

        // Required fields
        if (raw.SchemaVersion < 1) errors.Add("schema_version must be >= 1");
        if (string.IsNullOrWhiteSpace(raw.Id)) errors.Add("id is required");
        if (string.IsNullOrWhiteSpace(raw.Name)) errors.Add("name is required");
        if (string.IsNullOrWhiteSpace(raw.Version)) errors.Add("version is required");

        if (raw.Runtime is null) errors.Add("runtime is required");
        else if (string.IsNullOrWhiteSpace(raw.Runtime.Id)) errors.Add("runtime.id is required");

        if (raw.Entrypoint is null) errors.Add("entrypoint is required");
        else if (string.IsNullOrWhiteSpace(raw.Entrypoint.Type)) errors.Add("entrypoint.type is required");
        else if (!ValidEntrypointTypes.Contains(raw.Entrypoint.Type)) errors.Add($"Unknown entrypoint.type: {raw.Entrypoint.Type}");

        // Validate entrypoint fields per type
        if (raw.Entrypoint is not null && !string.IsNullOrWhiteSpace(raw.Entrypoint.Type))
        {
            ValidateEntrypointFields(raw.Entrypoint, errors);
        }

        if (errors.Count > 0)
        {
            _logger.LogWarning("Manifest validation failed: {Errors}", string.Join("; ", errors));
            return Task.FromResult(new ManifestValidationResult { IsValid = false, Errors = errors });
        }

        var manifest = MapToManifest(raw);
        return Task.FromResult(new ManifestValidationResult { IsValid = true, Manifest = manifest });
    }

    private static void ValidateEntrypointFields(ManifestEntrypointRaw ep, List<string> errors)
    {
        switch (ep.Type?.ToLowerInvariant())
        {
            case "python_function":
                if (string.IsNullOrWhiteSpace(ep.Module)) errors.Add("entrypoint.module is required for python_function");
                if (string.IsNullOrWhiteSpace(ep.Callable)) errors.Add("entrypoint.callable is required for python_function");
                break;
            case "python_module":
                if (string.IsNullOrWhiteSpace(ep.Module)) errors.Add("entrypoint.module is required for python_module");
                break;
            case "powershell_script":
                if (string.IsNullOrWhiteSpace(ep.Script)) errors.Add("entrypoint.script is required for powershell_script");
                break;
            case "executable":
                if (string.IsNullOrWhiteSpace(ep.Path)) errors.Add("entrypoint.path is required for executable");
                break;
            case "browser_playwright":
                if (string.IsNullOrWhiteSpace(ep.Module)) errors.Add("entrypoint.module is required for browser_playwright");
                break;
        }
    }

    private static AutomationManifest MapToManifest(ManifestRaw raw) => new()
    {
        SchemaVersion = raw.SchemaVersion,
        Id = raw.Id!,
        Name = raw.Name!,
        Version = raw.Version!,
        Description = raw.Description,
        Category = raw.Category,
        Runtime = new ManifestRuntime { Id = raw.Runtime!.Id!, Version = raw.Runtime.Version },
        Entrypoint = MapEntrypoint(raw.Entrypoint!),
        Capabilities = raw.Capabilities is not null
            ? new ManifestCapabilities { Required = raw.Capabilities.Required ?? Array.Empty<string>() }
            : null,
        Resources = raw.Resources is not null
            ? new ManifestResources
            {
                Pool = Enum.TryParse<PoolType>(raw.Resources.Pool, true, out var pt) ? pt : PoolType.Background,
                Slots = raw.Resources.Slots ?? 1,
                MaxMemoryMb = raw.Resources.MaxMemoryMb
            }
            : null,
        Timeout = raw.Timeout is not null
            ? new ManifestTimeout
            {
                ExecutionSeconds = raw.Timeout.ExecutionSeconds ?? 3600,
                GracefulShutdownSeconds = raw.Timeout.GracefulShutdownSeconds ?? 30
            }
            : null,
        Environment = raw.Environment
    };

    private static ManifestEntrypoint MapEntrypoint(ManifestEntrypointRaw raw)
    {
        var type = raw.Type!.ToLowerInvariant() switch
        {
            "python_function" => EntrypointType.PythonFunction,
            "python_module" => EntrypointType.PythonModule,
            "powershell_script" => EntrypointType.PowerShellScript,
            "executable" => EntrypointType.Executable,
            "browser_playwright" => EntrypointType.BrowserPlaywright,
            _ => EntrypointType.PythonFunction
        };
        return new ManifestEntrypoint
        {
            Type = type,
            Module = raw.Module,
            Callable = raw.Callable,
            Script = raw.Script,
            Path = raw.Path,
            Args = raw.Args
        };
    }

    // Internal raw deserialization models
    private sealed class ManifestRaw
    {
        public int SchemaVersion { get; set; }
        public string? Id { get; set; }
        public string? Name { get; set; }
        public string? Version { get; set; }
        public string? Description { get; set; }
        public string? Category { get; set; }
        public ManifestRuntimeRaw? Runtime { get; set; }
        public ManifestEntrypointRaw? Entrypoint { get; set; }
        public ManifestCapabilitiesRaw? Capabilities { get; set; }
        public ManifestResourcesRaw? Resources { get; set; }
        public ManifestTimeoutRaw? Timeout { get; set; }
        public Dictionary<string, string>? Environment { get; set; }
    }
    private sealed class ManifestRuntimeRaw { public string? Id { get; set; } public string? Version { get; set; } }
    private sealed class ManifestEntrypointRaw { public string? Type { get; set; } public string? Module { get; set; } public string? Callable { get; set; } public string? Script { get; set; } public string? Path { get; set; } public string? Args { get; set; } }
    private sealed class ManifestCapabilitiesRaw { public IReadOnlyList<string>? Required { get; set; } }
    private sealed class ManifestResourcesRaw { public string? Pool { get; set; } public int? Slots { get; set; } public long? MaxMemoryMb { get; set; } }
    private sealed class ManifestTimeoutRaw { public int? ExecutionSeconds { get; set; } public int? GracefulShutdownSeconds { get; set; } }
}
