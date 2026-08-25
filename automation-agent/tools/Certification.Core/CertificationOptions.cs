namespace Biason.AutomationAgent.Certification.Core;

/// <summary>
/// Configuration for one certification run. Nothing here is hardcoded —
/// every value is read from environment variables or CLI flags by
/// Certification.Cli (see docs/certification-harness.md, item 10: "Não
/// hardcode localhost em código de domínio"). Defaults exist only for local
/// developer convenience and always point at the documented dev stack
/// (README.md "Primeiro uso"), never at a specific machine's IP.
/// </summary>
public sealed class CertificationOptions
{
    /// <summary>Portal REST API base, e.g. http://localhost:8000/api/v1.</summary>
    public required string PortalApiBaseUrl { get; init; }

    /// <summary>Portal Agent Gateway WebSocket URL, e.g. ws://localhost:8000/api/v1/agent-gateway/connect.</summary>
    public required string PortalWebSocketUrl { get; init; }

    /// <summary>Root of the isolated certification data directory (item 8).</summary>
    public required string DataDirectory { get; init; }

    /// <summary>Path to the built Agent.Service binary/csproj to launch under certification config.</summary>
    public required string AgentServiceEntryPath { get; init; }

    /// <summary>True if <see cref="AgentServiceEntryPath"/> is a .csproj (launch via `dotnet run`) rather than a published .exe.</summary>
    public bool AgentServiceIsProject { get; init; } = true;

    public string AgentDisplayName { get; init; } = "certification-agent-01";

    public int PortalStartupTimeoutSeconds { get; init; } = 120;
    public int AgentStartupTimeoutSeconds { get; init; } = 120;
    public int ExecutionTimeoutSeconds { get; init; } = 120;
    public int GracefulShutdownTimeoutSeconds { get; init; } = 20;

    /// <summary>Admin credentials used only to call Portal admin endpoints
    /// (registration tokens, category/automation provisioning via the
    /// Python seed CLI). Read from environment, never written to
    /// appsettings.Certification.json or the report (item 21, item 78).</summary>
    public string AdminEmail { get; init; } = "admin@portal.local";
    public string AdminPassword { get; init; } = "admin123";

    public static CertificationOptions FromEnvironment(string repoRoot)
    {
        string Env(string name, string fallback) =>
            Environment.GetEnvironmentVariable(name) is { Length: > 0 } value ? value : fallback;

        var dataDir = Env(
            "CERTIFICATION_DATA_DIR",
            Path.Combine(repoRoot, "automation-agent", "certification-runs", "agent-data"));

        return new CertificationOptions
        {
            PortalApiBaseUrl = Env("CERTIFICATION_PORTAL_API_URL", "http://localhost:8000/api/v1"),
            PortalWebSocketUrl = Env(
                "CERTIFICATION_PORTAL_WS_URL", "ws://localhost:8000/api/v1/agent-gateway/connect"),
            DataDirectory = dataDir,
            AgentServiceEntryPath = Env(
                "CERTIFICATION_AGENT_SERVICE_PROJECT",
                Path.Combine(repoRoot, "automation-agent", "src", "Agent.Service", "Agent.Service.csproj")),
            AdminEmail = Env("CERTIFICATION_ADMIN_EMAIL", "admin@portal.local"),
            AdminPassword = Env("CERTIFICATION_ADMIN_PASSWORD", "admin123"),
        };
    }
}
