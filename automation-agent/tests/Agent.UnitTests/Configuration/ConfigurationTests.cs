using Biason.AutomationAgent.Domain.Configuration;
using FluentAssertions;
using Xunit;

namespace Biason.AutomationAgent.UnitTests.Configuration;

public class ConfigurationTests
{
    [Fact]
    public void AgentOptions_Defaults_AreValid()
    {
        var opts = new AgentOptions();
        opts.Profile.Should().Be("workstation");
        opts.Version.Should().Be("0.1.0");
        opts.Name.Should().BeNull();
    }

    [Fact]
    public void MonitoringOptions_Defaults_AreValid()
    {
        var opts = new MonitoringOptions();
        opts.SampleIntervalSeconds.Should().Be(5);
        opts.HistoryRetentionMinutes.Should().Be(60);
    }

    [Fact]
    public void StorageOptions_Defaults_AreValid()
    {
        var opts = new StorageOptions();
        opts.MinimumFreeDiskMb.Should().Be(2048);
    }

    [Fact]
    public void DatabaseOptions_Defaults_AreValid()
    {
        var opts = new DatabaseOptions();
        opts.BusyTimeoutMs.Should().Be(5000);
        opts.JournalMode.Should().Be("WAL");
    }
}
