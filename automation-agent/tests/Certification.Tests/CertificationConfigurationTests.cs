using System.ComponentModel.DataAnnotations;
using System.Reflection;
using System.Text.Json;
using Biason.AutomationAgent.Domain.Configuration;
using FluentAssertions;
using Xunit;

namespace Biason.AutomationAgent.Certification.Tests;

public class CertificationConfigurationTests
{
    [Fact]
    public void AgentProfile_UsesDomainAllowedValue()
    {
        var repoRoot = FindRepoRoot();
        var configPath = Path.Combine(repoRoot, "src", "Agent.Service", "appsettings.Certification.json");
        using var doc = JsonDocument.Parse(File.ReadAllText(configPath));
        var profile = doc.RootElement
            .GetProperty(AgentOptions.Section)
            .GetProperty(nameof(AgentOptions.Profile))
            .GetString();

        var allowed = typeof(AgentOptions)
            .GetProperty(nameof(AgentOptions.Profile))!
            .GetCustomAttribute<AllowedValuesAttribute>()!
            .Values
            .Cast<object>()
            .Select(value => value.ToString())
            .ToArray();

        profile.Should().BeOneOf(allowed);
    }

    private static string FindRepoRoot()
    {
        var directory = new DirectoryInfo(AppContext.BaseDirectory);
        while (directory is not null)
        {
            var candidate = Path.Combine(directory.FullName, "src", "Agent.Service", "appsettings.Certification.json");
            if (File.Exists(candidate))
                return directory.FullName;

            directory = directory.Parent;
        }

        throw new DirectoryNotFoundException("Could not locate automation-agent repository root.");
    }
}
