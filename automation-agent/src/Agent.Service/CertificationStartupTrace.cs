internal static class CertificationStartupTrace
{
    public static void Write(string stage)
    {
        var environment = Environment.GetEnvironmentVariable("DOTNET_ENVIRONMENT");
        var enabled = string.Equals(environment, "Certification", StringComparison.OrdinalIgnoreCase) ||
            string.Equals(Environment.GetEnvironmentVariable("AUTOMATION_AGENT_CERTIFICATION_TRACE"), "true", StringComparison.OrdinalIgnoreCase);
        if (!enabled)
            return;

        var root = Environment.GetEnvironmentVariable("AUTOMATION_AGENT_DATA_DIR");
        if (string.IsNullOrWhiteSpace(root))
            return;

        try
        {
            var diagnostics = Path.Combine(root, "diagnostics");
            Directory.CreateDirectory(diagnostics);
            var line = $"{DateTimeOffset.UtcNow:O} pid={Environment.ProcessId} stage={stage}{Environment.NewLine}";
            File.AppendAllText(Path.Combine(diagnostics, "startup-trace.log"), line);
        }
        catch
        {
            // Best-effort certification diagnostics must never affect Agent startup.
        }
    }
}
