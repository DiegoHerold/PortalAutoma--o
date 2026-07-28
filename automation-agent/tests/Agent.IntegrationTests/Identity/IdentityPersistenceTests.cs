using Biason.AutomationAgent.IntegrationTests.Helpers;
using FluentAssertions;
using Xunit;

namespace Biason.AutomationAgent.IntegrationTests.Identity;

public class IdentityPersistenceTests : IDisposable
{
    private readonly TestHelper _helper = new();

    [Fact]
    public async Task GetOrCreateIdentity_CreatesNewIdentity()
    {
        await _helper.InitializeDatabaseAsync();
        var repo = _helper.CreateIdentityRepository();

        var identity = await repo.GetOrCreateIdentityAsync();

        identity.Should().NotBeNull();
        identity.InstallationId.Should().StartWith("ins_");
        identity.MachineId.Should().StartWith("mch_");
        identity.InstanceId.Should().NotBeNullOrEmpty();
        identity.AgentId.Should().BeNull();
        identity.CreatedAtUtc.Should().BeCloseTo(DateTime.UtcNow, TimeSpan.FromSeconds(5));
    }

    [Fact]
    public async Task GetOrCreateIdentity_PreservesExistingIdentity()
    {
        await _helper.InitializeDatabaseAsync();
        var repo1 = _helper.CreateIdentityRepository();
        var first = await repo1.GetOrCreateIdentityAsync();

        // Simulate restart by creating new repository
        var repo2 = _helper.CreateIdentityRepository();
        var second = await repo2.GetOrCreateIdentityAsync();

        second.InstallationId.Should().Be(first.InstallationId);
        second.MachineId.Should().Be(first.MachineId);
        // InstanceId should differ (new process)
        second.InstanceId.Should().NotBe(first.InstanceId);
    }

    [Fact]
    public async Task UpdateAgentId_PersistsCorrectly()
    {
        await _helper.InitializeDatabaseAsync();
        var repo = _helper.CreateIdentityRepository();
        await repo.GetOrCreateIdentityAsync();

        await repo.UpdateAgentIdAsync("agt_test_123");

        var identity = await repo.GetIdentityAsync();
        identity!.AgentId.Should().Be("agt_test_123");
        identity.RegisteredAtUtc.Should().NotBeNull();
    }

    public void Dispose() => _helper.Dispose();
}
