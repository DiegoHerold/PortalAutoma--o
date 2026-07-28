using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models;
using Biason.AutomationAgent.IntegrationTests.Helpers;
using FluentAssertions;
using Xunit;

namespace Biason.AutomationAgent.IntegrationTests.Persistence;

public class CapabilityRepositoryTests : IDisposable
{
    private readonly TestHelper _helper = new();

    [Fact]
    public async Task SaveAndRetrieve_Works()
    {
        await _helper.InitializeDatabaseAsync();
        var repo = _helper.CreateCapabilityRepository();

        var caps = new List<Capability>
        {
            new() { Key = "windows", Status = CapabilityStatus.Available, Version = "10.0", Source = "runtime", DetectedAtUtc = DateTime.UtcNow },
            new() { Key = "browser.chrome", Status = CapabilityStatus.Available, Version = "126.0", Source = "registry", DetectedAtUtc = DateTime.UtcNow,
                Details = new() { ["executable_path"] = @"C:\Chrome\chrome.exe" } },
            new() { Key = "browser.firefox", Status = CapabilityStatus.Unavailable, Source = "detection", DetectedAtUtc = DateTime.UtcNow }
        };

        await repo.SaveAllAsync(caps);

        var loaded = await repo.GetAllAsync();
        loaded.Should().HaveCount(3);
        loaded.Should().Contain(c => c.Key == "browser.chrome" && c.Status == CapabilityStatus.Available);
        loaded.First(c => c.Key == "browser.chrome").Details.Should().ContainKey("executable_path");
    }

    [Fact]
    public async Task SaveAll_ReplacesExisting()
    {
        await _helper.InitializeDatabaseAsync();
        var repo = _helper.CreateCapabilityRepository();

        await repo.SaveAllAsync(new List<Capability>
        {
            new() { Key = "windows", Status = CapabilityStatus.Available, DetectedAtUtc = DateTime.UtcNow }
        });

        await repo.SaveAllAsync(new List<Capability>
        {
            new() { Key = "windows", Status = CapabilityStatus.Degraded, DetectedAtUtc = DateTime.UtcNow }
        });

        var loaded = await repo.GetAllAsync();
        loaded.Should().HaveCount(1);
        loaded[0].Status.Should().Be(CapabilityStatus.Degraded);
    }

    public void Dispose() => _helper.Dispose();
}
