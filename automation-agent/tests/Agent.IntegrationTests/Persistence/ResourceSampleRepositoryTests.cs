using Biason.AutomationAgent.Domain.Models;
using Biason.AutomationAgent.IntegrationTests.Helpers;
using FluentAssertions;
using Xunit;

namespace Biason.AutomationAgent.IntegrationTests.Persistence;

public class ResourceSampleRepositoryTests : IDisposable
{
    private readonly TestHelper _helper = new();

    [Fact]
    public async Task SaveAndRetrieve_Works()
    {
        await _helper.InitializeDatabaseAsync();
        var repo = _helper.CreateResourceSampleRepository();

        var sample = new ResourceSample
        {
            SampledAtUtc = DateTime.UtcNow,
            CpuUsagePercent = 25.5,
            MemoryTotalMb = 16384,
            MemoryAvailableMb = 10000,
            MemoryUsedMb = 6384,
            MemoryUsagePercent = 39.0,
            DiskTotalMb = 500000,
            DiskFreeMb = 200000,
            DiskUsagePercent = 60.0,
            AgentMemoryMb = 85,
            ProcessCount = 150,
            UptimeSeconds = 86400
        };

        await repo.SaveAsync(sample);

        var latest = await repo.GetLatestAsync();
        latest.Should().NotBeNull();
        latest!.CpuUsagePercent.Should().Be(25.5);
        latest.MemoryTotalMb.Should().Be(16384);
    }

    [Fact]
    public async Task GetRecent_ReturnsCorrectTimeRange()
    {
        await _helper.InitializeDatabaseAsync();
        var repo = _helper.CreateResourceSampleRepository();

        for (int i = 0; i < 5; i++)
        {
            await repo.SaveAsync(new ResourceSample
            {
                SampledAtUtc = DateTime.UtcNow.AddMinutes(-i),
                CpuUsagePercent = i * 10,
                MemoryTotalMb = 16384,
                MemoryAvailableMb = 10000,
                MemoryUsedMb = 6384,
                MemoryUsagePercent = 39,
                DiskTotalMb = 500000,
                DiskFreeMb = 200000,
                DiskUsagePercent = 60,
                AgentMemoryMb = 85,
                ProcessCount = 150,
                UptimeSeconds = 86400
            });
        }

        var recent = await repo.GetRecentAsync(3);
        recent.Should().HaveCountGreaterOrEqualTo(3);
    }

    [Fact]
    public async Task PurgeOlderThan_RemovesOldRecords()
    {
        await _helper.InitializeDatabaseAsync();
        var repo = _helper.CreateResourceSampleRepository();

        await repo.SaveAsync(new ResourceSample
        {
            SampledAtUtc = DateTime.UtcNow.AddHours(-2),
            CpuUsagePercent = 10, MemoryTotalMb = 16384, MemoryAvailableMb = 10000,
            MemoryUsedMb = 6384, MemoryUsagePercent = 39, DiskTotalMb = 500000,
            DiskFreeMb = 200000, DiskUsagePercent = 60, AgentMemoryMb = 85,
            ProcessCount = 150, UptimeSeconds = 86400
        });

        await repo.SaveAsync(new ResourceSample
        {
            SampledAtUtc = DateTime.UtcNow,
            CpuUsagePercent = 20, MemoryTotalMb = 16384, MemoryAvailableMb = 10000,
            MemoryUsedMb = 6384, MemoryUsagePercent = 39, DiskTotalMb = 500000,
            DiskFreeMb = 200000, DiskUsagePercent = 60, AgentMemoryMb = 85,
            ProcessCount = 150, UptimeSeconds = 86400
        });

        await repo.PurgeOlderThanAsync(DateTime.UtcNow.AddHours(-1));

        var remaining = await repo.GetRecentAsync(180);
        remaining.Should().HaveCount(1);
        remaining[0].CpuUsagePercent.Should().Be(20);
    }

    public void Dispose() => _helper.Dispose();
}
