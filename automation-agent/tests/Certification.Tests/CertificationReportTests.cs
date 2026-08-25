using Biason.AutomationAgent.Certification.Core.Reporting;
using FluentAssertions;
using Xunit;

namespace Biason.AutomationAgent.Certification.Tests;

public class CertificationReportTests
{
    private static CertificationReport NewReport() => new()
    {
        RunId = "cert_20260806_001",
        StartedAtUtc = DateTimeOffset.UtcNow
    };

    [Fact]
    public void OverallGate_NoScenarios_IsBlocked()
    {
        NewReport().OverallGate.Should().Be("BLOCKED");
    }

    [Fact]
    public void OverallGate_AllPass_IsPass()
    {
        var report = NewReport();
        report.Scenarios.Add(new ScenarioResult { ScenarioId = "certification.echo", Mode = CertificationMode.PortalE2E, Status = ScenarioStatus.Pass });
        report.Scenarios.Add(new ScenarioResult { ScenarioId = "certification.fail", Mode = CertificationMode.PortalE2E, Status = ScenarioStatus.Pass });
        report.OverallGate.Should().Be("PASS");
    }

    [Fact]
    public void OverallGate_AnyFail_IsFail_EvenIfOthersPass()
    {
        var report = NewReport();
        report.Scenarios.Add(new ScenarioResult { ScenarioId = "certification.echo", Mode = CertificationMode.PortalE2E, Status = ScenarioStatus.Pass });
        report.Scenarios.Add(new ScenarioResult { ScenarioId = "certification.timeout", Mode = CertificationMode.PortalE2E, Status = ScenarioStatus.Fail });
        report.OverallGate.Should().Be("FAIL");
    }

    [Fact]
    public void OverallGate_BlockedWithoutFail_IsBlocked_NeverPass()
    {
        // Item 51: a harness poll timeout must never be reported as PASS.
        var report = NewReport();
        report.Scenarios.Add(new ScenarioResult { ScenarioId = "certification.echo", Mode = CertificationMode.PortalE2E, Status = ScenarioStatus.Pass });
        report.Scenarios.Add(new ScenarioResult { ScenarioId = "certification.progress", Mode = CertificationMode.PortalE2E, Status = ScenarioStatus.Blocked });
        report.OverallGate.Should().Be("BLOCKED");
    }

    [Fact]
    public void Save_RefusesToWriteBearerToken()
    {
        var report = NewReport();
        report.Scenarios.Add(new ScenarioResult
        {
            ScenarioId = "certification.echo",
            Mode = CertificationMode.PortalE2E,
            Status = ScenarioStatus.Pass,
            Notes = "Bearer abcdef1234567890abcdef" // must never end up in a saved report
        });

        var path = Path.Combine(Path.GetTempPath(), $"cert-report-test-{Guid.NewGuid():N}.json");
        try
        {
            var act = () => report.Save(path);
            act.Should().Throw<InvalidOperationException>();
            File.Exists(path).Should().BeFalse();
        }
        finally
        {
            if (File.Exists(path)) File.Delete(path);
        }
    }

    [Fact]
    public void Save_WritesValidJsonForCleanReport()
    {
        var report = NewReport();
        report.Scenarios.Add(new ScenarioResult { ScenarioId = "certification.echo", Mode = CertificationMode.PortalE2E, Status = ScenarioStatus.Pass });

        var path = Path.Combine(Path.GetTempPath(), $"cert-report-test-{Guid.NewGuid():N}.json");
        try
        {
            report.Save(path);
            File.Exists(path).Should().BeTrue();
            File.ReadAllText(path).Should().Contain("\"RunId\"").And.Contain("certification.echo");
        }
        finally
        {
            if (File.Exists(path)) File.Delete(path);
        }
    }
}
