using Biason.AutomationAgent.Application.Execution;
using Biason.AutomationAgent.Domain.Contracts;
using FluentAssertions;
using Microsoft.Extensions.Logging;
using NSubstitute;
using Xunit;

namespace Biason.AutomationAgent.UnitTests.Execution;

public class ResultCollectorTests : IDisposable
{
    private readonly ResultCollector _sut;
    private readonly string _workspacePath;

    public ResultCollectorTests()
    {
        var clock = Substitute.For<IClock>();
        clock.UtcNow.Returns(new DateTime(2026, 7, 28, 15, 0, 0, DateTimeKind.Utc));
        var logger = Substitute.For<ILogger<ResultCollector>>();
        _sut = new ResultCollector(clock, logger);
        _workspacePath = Path.Combine(Path.GetTempPath(), $"rc_test_{Guid.NewGuid():N}");
        Directory.CreateDirectory(Path.Combine(_workspacePath, "output"));
        Directory.CreateDirectory(Path.Combine(_workspacePath, "artifacts"));
        Directory.CreateDirectory(Path.Combine(_workspacePath, "logs"));
    }

    [Fact]
    public async Task Collect_WithExitCodeZero_ReturnsSuccess()
    {
        var result = await _sut.CollectAsync("exec_1", "att_1", _workspacePath, 0);

        result.Success.Should().BeTrue();
        result.ExitCode.Should().Be(0);
        result.ExecutionId.Should().Be("exec_1");
    }

    [Fact]
    public async Task Collect_WithExitCodeNonZero_ReturnsFailure()
    {
        var result = await _sut.CollectAsync("exec_2", "att_1", _workspacePath, 1);

        result.Success.Should().BeFalse();
        result.ExitCode.Should().Be(1);
    }

    [Fact]
    public async Task Collect_WithOutputFile_ReadsOutput()
    {
        var outputPath = Path.Combine(_workspacePath, "output", "output.json");
        await File.WriteAllTextAsync(outputPath, """{"processed": 42}""");

        var result = await _sut.CollectAsync("exec_3", "att_1", _workspacePath, 0);

        result.OutputJson.Should().Contain("42");
    }

    [Fact]
    public async Task Collect_WithArtifacts_CollectsFiles()
    {
        var artifactFile = Path.Combine(_workspacePath, "artifacts", "report.txt");
        await File.WriteAllTextAsync(artifactFile, "test report");

        var result = await _sut.CollectAsync("exec_4", "att_1", _workspacePath, 0);

        result.Artifacts.Should().HaveCount(1);
        result.Artifacts[0].Name.Should().Be("report.txt");
        result.Artifacts[0].ContentType.Should().Be("text/plain");
        result.Artifacts[0].SizeBytes.Should().BeGreaterThan(0);
    }

    [Fact]
    public async Task Collect_SkipsStepImages_AlreadyUploadedDuringTheRun()
    {
        Directory.CreateDirectory(Path.Combine(_workspacePath, "artifacts", "passos"));
        await File.WriteAllBytesAsync(Path.Combine(_workspacePath, "artifacts", "passos", "img_1.jpg"), new byte[] { 0xFF, 0xD8, 0xFF });
        await File.WriteAllTextAsync(Path.Combine(_workspacePath, "artifacts", "report.txt"), "test report");

        var result = await _sut.CollectAsync("exec_5", "att_1", _workspacePath, 0);

        result.Artifacts.Select(a => a.Name).Should().Equal("report.txt");
    }

    [Fact]
    public async Task Collect_WithStderr_ReadsError()
    {
        var stderrPath = Path.Combine(_workspacePath, "logs", "stderr.log");
        await File.WriteAllTextAsync(stderrPath, "Something went wrong");

        var result = await _sut.CollectAsync("exec_5", "att_1", _workspacePath, 1);

        result.ErrorOutput.Should().Contain("Something went wrong");
    }

    [Fact]
    public async Task Collect_WithMetrics_ReadsMetrics()
    {
        var metricsPath = Path.Combine(_workspacePath, "output", "metrics.json");
        await File.WriteAllTextAsync(metricsPath, """{"duration_ms": 5000, "peak_memory_mb": 128, "cpu_time_seconds": 2.5}""");

        var result = await _sut.CollectAsync("exec_6", "att_1", _workspacePath, 0);

        result.DurationMs.Should().Be(5000);
        result.PeakMemoryMb.Should().Be(128);
        result.CpuTimeSeconds.Should().Be(2.5);
    }

    public void Dispose()
    {
        try { Directory.Delete(_workspacePath, true); } catch { }
    }
}
