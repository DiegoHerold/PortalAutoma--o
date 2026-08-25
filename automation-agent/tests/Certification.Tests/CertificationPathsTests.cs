using Biason.AutomationAgent.Certification.Core;
using FluentAssertions;
using Xunit;

namespace Biason.AutomationAgent.Certification.Tests;

public class CertificationPathsTests
{
    [Fact]
    public void NextRunId_FirstRunOfDay_UsesSequence001()
    {
        var repoRoot = Path.Combine(Path.GetTempPath(), $"cert-repo-{Guid.NewGuid():N}");
        Directory.CreateDirectory(repoRoot);
        try
        {
            var runId = CertificationPaths.NextRunId(repoRoot, new DateTime(2026, 8, 6, 0, 0, 0, DateTimeKind.Utc));
            runId.Should().Be("cert_20260806_001");
        }
        finally
        {
            Directory.Delete(repoRoot, recursive: true);
        }
    }

    [Fact]
    public void NextRunId_IsIdempotentAndSkipsExistingRuns()
    {
        var repoRoot = Path.Combine(Path.GetTempPath(), $"cert-repo-{Guid.NewGuid():N}");
        var date = new DateTime(2026, 8, 6, 0, 0, 0, DateTimeKind.Utc);
        Directory.CreateDirectory(Path.Combine(repoRoot, "automation-agent", "certification-runs", "cert_20260806_001"));
        try
        {
            var runId = CertificationPaths.NextRunId(repoRoot, date);
            runId.Should().Be("cert_20260806_002");
        }
        finally
        {
            Directory.Delete(repoRoot, recursive: true);
        }
    }

    [Fact]
    public void EnsureDirectoriesExist_CreatesExpectedLayout()
    {
        var repoRoot = Path.Combine(Path.GetTempPath(), $"cert-repo-{Guid.NewGuid():N}");
        try
        {
            var paths = new CertificationPaths(repoRoot, "cert_test_001");
            paths.EnsureDirectoriesExist();

            Directory.Exists(paths.RunRoot).Should().BeTrue();
            Directory.Exists(paths.PortalLogsPath).Should().BeTrue();
            Directory.Exists(paths.AgentLogsPath).Should().BeTrue();
            Directory.Exists(paths.ExecutionsPath).Should().BeTrue();
            Directory.Exists(paths.PidDirectory).Should().BeTrue();
        }
        finally
        {
            if (Directory.Exists(repoRoot)) Directory.Delete(repoRoot, recursive: true);
        }
    }
}
