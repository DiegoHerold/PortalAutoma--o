using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace Biason.AutomationAgent.Windows.Detection;

public sealed class WindowsCapabilityDetector : ICapabilityDetector
{
    private readonly ISoftwareDetector _softwareDetector;
    private readonly ISessionInfoCollector _sessionCollector;
    private readonly IClock _clock;
    private readonly CapacityOptions _capacityOptions;
    private readonly ILogger<WindowsCapabilityDetector> _logger;

    public WindowsCapabilityDetector(
        ISoftwareDetector softwareDetector,
        ISessionInfoCollector sessionCollector,
        IClock clock,
        IOptions<CapacityOptions> capacityOptions,
        ILogger<WindowsCapabilityDetector> logger)
    {
        _softwareDetector = softwareDetector;
        _sessionCollector = sessionCollector;
        _clock = clock;
        _capacityOptions = capacityOptions.Value;
        _logger = logger;
    }

    public Task<IReadOnlyList<Capability>> DetectAllAsync(CancellationToken ct = default)
    {
        var now = _clock.UtcNow;
        var capabilities = new List<Capability>();
        var software = _softwareDetector.DetectAll();
        var session = _sessionCollector.Collect();

        // OS capabilities
        capabilities.Add(new Capability
        {
            Key = "windows",
            Status = CapabilityStatus.Available,
            Version = Environment.OSVersion.Version.ToString(),
            Source = "runtime",
            DetectedAtUtc = now
        });

        capabilities.Add(new Capability
        {
            Key = "windows.x64",
            Status = Environment.Is64BitOperatingSystem ? CapabilityStatus.Available : CapabilityStatus.Unavailable,
            Source = "runtime",
            DetectedAtUtc = now
        });

        // PowerShell
        var ps = software.FirstOrDefault(s => s.Name == "PowerShell");
        capabilities.Add(new Capability
        {
            Key = "powershell",
            Status = ps?.IsInstalled == true ? CapabilityStatus.Available : CapabilityStatus.Unavailable,
            Version = ps?.Version,
            Source = ps?.Source ?? "filesystem",
            DetectedAtUtc = now,
            Details = ps?.ExecutablePath is not null ? new() { ["executable_path"] = ps.ExecutablePath } : null
        });

        // Browsers
        AddSoftwareCapability(capabilities, software, "Google Chrome", "browser.chrome", now);
        AddSoftwareCapability(capabilities, software, "Microsoft Edge", "browser.edge", now);
        AddSoftwareCapability(capabilities, software, "WebView2", "browser.webview2", now);

        // Office
        AddSoftwareCapability(capabilities, software, "Microsoft Excel", "office.excel", now);

        // Domínio
        AddSoftwareCapability(capabilities, software, "Dominio Contabil", "dominio.installed", now);

        // Desktop automation capabilities (future)
        capabilities.Add(new Capability
        {
            Key = "desktop_automation",
            Status = CapabilityStatus.NotConfigured,
            Source = "agent",
            DetectedAtUtc = now
        });

        // Session capabilities
        capabilities.Add(new Capability
        {
            Key = "interactive_session",
            Status = session.Status == SessionStatus.Available ? CapabilityStatus.Available : CapabilityStatus.Unavailable,
            Source = "runtime",
            DetectedAtUtc = now,
            Details = session.SessionId.HasValue ? new() { ["session_id"] = session.SessionId.Value.ToString() } : null
        });

        capabilities.Add(new Capability
        {
            Key = session.Type == SessionType.Rdp ? "rdp_session" : "local_session",
            Status = session.Status == SessionStatus.Available ? CapabilityStatus.Available : CapabilityStatus.Unavailable,
            Source = "runtime",
            DetectedAtUtc = now
        });

        // Agent execution types (architectural preparation)
        capabilities.Add(new Capability
        {
            Key = "agent.background_execution",
            Status = _capacityOptions.BackgroundPoolSize > 0 ? CapabilityStatus.Available : CapabilityStatus.NotConfigured,
            Source = "agent",
            DetectedAtUtc = now
        });

        capabilities.Add(new Capability
        {
            Key = "agent.browser_execution",
            Status = _capacityOptions.BrowserPoolSize > 0 ? CapabilityStatus.Available : CapabilityStatus.NotConfigured,
            Source = "agent",
            DetectedAtUtc = now
        });

        capabilities.Add(new Capability
        {
            Key = "agent.interactive_execution",
            Status = _capacityOptions.InteractivePoolSize > 0 ? CapabilityStatus.Available : CapabilityStatus.NotConfigured,
            Source = "agent",
            DetectedAtUtc = now
        });

        _logger.LogInformation("Detected {Count} capabilities", capabilities.Count);
        return Task.FromResult<IReadOnlyList<Capability>>(capabilities);
    }

    private static void AddSoftwareCapability(List<Capability> caps, IReadOnlyList<InstalledSoftware> software, string name, string key, DateTime now)
    {
        var sw = software.FirstOrDefault(s => s.Name == name);
        caps.Add(new Capability
        {
            Key = key,
            Status = sw?.IsInstalled == true ? CapabilityStatus.Available : CapabilityStatus.Unavailable,
            Version = sw?.Version,
            Source = sw?.Source ?? "detection",
            DetectedAtUtc = now,
            Details = sw?.ExecutablePath is not null ? new() { ["executable_path"] = sw.ExecutablePath } : null
        });
    }
}
