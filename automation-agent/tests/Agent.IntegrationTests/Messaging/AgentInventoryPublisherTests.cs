using System.Text.Json;
using Biason.AutomationAgent.Application.Messaging;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models;
using Biason.AutomationAgent.IntegrationTests.Helpers;
using Biason.AutomationAgent.Protocol.Messages;
using FluentAssertions;
using Microsoft.Extensions.Logging.Abstractions;
using Xunit;

namespace Biason.AutomationAgent.IntegrationTests.Messaging;

public sealed class AgentInventoryPublisherTests : IAsyncLifetime
{
    private readonly TestHelper _helper = new();

    public async Task InitializeAsync()
    {
        await _helper.InitializeDatabaseAsync();
        await _helper.SeedRegisteredAgentAsync(agentId: "agt_inventory", credentialValue: "segredo-teste");
    }

    public Task DisposeAsync()
    {
        _helper.Dispose();
        return Task.CompletedTask;
    }

    [Fact]
    public async Task PublishCapabilitiesAsync_EnqueuesRealDetectedCapabilities()
    {
        var capabilities = _helper.CreateCapabilityRepository();
        await capabilities.SaveAllAsync(new[]
        {
            new Capability
            {
                Key = "windows",
                Status = CapabilityStatus.Available,
                Version = "10.0",
                Source = "os",
                DetectedAtUtc = _helper.Clock.UtcNow,
                Details = new() { ["edition"] = "test" }
            },
            new Capability
            {
                Key = "agent.background_execution",
                Status = CapabilityStatus.Available,
                Source = "agent",
                DetectedAtUtc = _helper.Clock.UtcNow
            }
        });

        var outbox = _helper.CreateOutboxRepository();
        var publisher = new AgentInventoryPublisher(
            capabilities,
            _helper.CreateIdentityRepository(),
            new OutboxMessagePublisher(outbox, _helper.CreateIdentityRepository(), _helper.Clock),
            _helper.Clock,
            NullLogger<AgentInventoryPublisher>.Instance);

        await publisher.PublishCapabilitiesAsync("test");

        var message = (await outbox.GetReadyBatchAsync(10, _helper.Clock.UtcNow)).Single();
        message.MessageType.Should().Be(PortalMessageTypes.CapabilitiesUpdated);

        using var document = JsonDocument.Parse(message.PayloadJson);
        var root = document.RootElement;
        root.GetProperty("agent_id").GetString().Should().Be("agt_inventory");
        root.GetProperty("capabilities").EnumerateArray()
            .Select(item => item.GetProperty("key").GetString())
            .Should().Contain(new[] { "windows", "agent.background_execution" });
        root.GetProperty("capabilities").EnumerateArray()
            .First(item => item.GetProperty("key").GetString() == "windows")
            .GetProperty("status").GetString()
            .Should().Be("available");
    }
}
