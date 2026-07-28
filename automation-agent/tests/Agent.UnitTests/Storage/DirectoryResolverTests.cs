using Biason.AutomationAgent.Infrastructure.Storage;
using FluentAssertions;
using Microsoft.Extensions.Logging;
using NSubstitute;
using Xunit;

namespace Biason.AutomationAgent.UnitTests.Storage;

public class DirectoryResolverTests
{
    [Fact]
    public void Constructor_WithOverridePath_UsesIt()
    {
        var logger = Substitute.For<ILogger<AgentDirectoryResolver>>();
        var resolver = new AgentDirectoryResolver(logger, @"C:\TestAgent");

        resolver.RootPath.Should().Be(@"C:\TestAgent");
        resolver.DatabaseFilePath.Should().Contain("agent.db");
    }

    [Fact]
    public void AllPaths_AreUnderRoot()
    {
        var logger = Substitute.For<ILogger<AgentDirectoryResolver>>();
        var resolver = new AgentDirectoryResolver(logger, @"C:\TestAgent");

        resolver.ConfigPath.Should().StartWith(@"C:\TestAgent");
        resolver.DatabasePath.Should().StartWith(@"C:\TestAgent");
        resolver.LogsPath.Should().StartWith(@"C:\TestAgent");
        resolver.SpoolPath.Should().StartWith(@"C:\TestAgent");
        resolver.DiagnosticsPath.Should().StartWith(@"C:\TestAgent");
        resolver.StorePath.Should().StartWith(@"C:\TestAgent");
        resolver.RuntimesPath.Should().StartWith(@"C:\TestAgent");
        resolver.PackagesPath.Should().StartWith(@"C:\TestAgent");
        resolver.DownloadsPath.Should().StartWith(@"C:\TestAgent");
        resolver.StagingPath.Should().StartWith(@"C:\TestAgent");
        resolver.ExecutionsPath.Should().StartWith(@"C:\TestAgent");
        resolver.ArtifactsPath.Should().StartWith(@"C:\TestAgent");
    }

    [Fact]
    public void Validate_ValidPath_ReturnsTrue()
    {
        var logger = Substitute.For<ILogger<AgentDirectoryResolver>>();
        var resolver = new AgentDirectoryResolver(logger, @"C:\TestAgent");

        var result = resolver.Validate(out var errors);
        result.Should().BeTrue();
        errors.Should().BeEmpty();
    }

    [Fact]
    public void EnsureDirectoriesExist_CreatesAll()
    {
        var tempDir = Path.Combine(Path.GetTempPath(), $"agent-test-{Guid.NewGuid():N}");
        try
        {
            var logger = Substitute.For<ILogger<AgentDirectoryResolver>>();
            var resolver = new AgentDirectoryResolver(logger, tempDir);

            resolver.EnsureDirectoriesExist();

            Directory.Exists(resolver.ConfigPath).Should().BeTrue();
            Directory.Exists(resolver.DatabasePath).Should().BeTrue();
            Directory.Exists(resolver.LogsPath).Should().BeTrue();
            Directory.Exists(resolver.SpoolPath).Should().BeTrue();
            Directory.Exists(resolver.DiagnosticsPath).Should().BeTrue();

            // Idempotency: run again, should not throw
            var act = () => resolver.EnsureDirectoriesExist();
            act.Should().NotThrow();
        }
        finally
        {
            if (Directory.Exists(tempDir))
                Directory.Delete(tempDir, recursive: true);
        }
    }
}
