using Biason.AutomationAgent.Domain.Enums;

namespace Biason.AutomationAgent.Domain.Models;

public sealed class AutomationManifest
{
    public int SchemaVersion { get; init; } = 1;
    public string Id { get; init; } = default!;
    public string Name { get; init; } = default!;
    public string Version { get; init; } = default!;
    public string? Description { get; init; }
    public string? Category { get; init; }
    public ManifestRuntime Runtime { get; init; } = default!;
    public ManifestEntrypoint Entrypoint { get; init; } = default!;
    public ManifestCapabilities? Capabilities { get; init; }
    public ManifestResources? Resources { get; init; }
    public ManifestTimeout? Timeout { get; init; }
    public Dictionary<string, string>? Environment { get; init; }
}

public sealed class ManifestRuntime
{
    public string Id { get; init; } = default!;
    public string? Version { get; init; }
}

public sealed class ManifestEntrypoint
{
    public EntrypointType Type { get; init; }
    public string? Module { get; init; }
    public string? Callable { get; init; }
    public string? Script { get; init; }
    public string? Path { get; init; }
    public string? Args { get; init; }
}

public sealed class ManifestCapabilities
{
    public IReadOnlyList<string> Required { get; init; } = Array.Empty<string>();
}

public sealed class ManifestResources
{
    public PoolType Pool { get; init; } = PoolType.Background;
    public int Slots { get; init; } = 1;
    public long? MaxMemoryMb { get; init; }
}

public sealed class ManifestTimeout
{
    public int ExecutionSeconds { get; init; } = 3600;
    public int GracefulShutdownSeconds { get; init; } = 30;
}
