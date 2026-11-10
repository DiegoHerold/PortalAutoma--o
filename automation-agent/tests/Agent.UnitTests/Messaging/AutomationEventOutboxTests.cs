using System.Text.Json;
using Biason.AutomationAgent.Application.Messaging;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Models.Messaging;
using Biason.AutomationAgent.Protocol.Messages;
using FluentAssertions;
using NSubstitute;
using Xunit;

namespace Biason.AutomationAgent.UnitTests.Messaging;

public sealed class AutomationEventOutboxTests
{
    [Fact]
    public async Task EventoDaAutomacao_ViraEventBatchComOEventoIntacto()
    {
        var outbox = Substitute.For<IOutboxRepository>();
        OutboxMessageDraft? gravado = null;
        outbox.EnqueueAsync(Arg.Do<OutboxMessageDraft>(d => gravado = d), Arg.Any<CancellationToken>())
            .Returns(_ => new OutboxMessage());
        var identity = Substitute.For<IAgentIdentityService>();
        var clock = Substitute.For<IClock>();
        clock.UtcNow.Returns(new DateTime(2026, 11, 9, 14, 0, 0, DateTimeKind.Utc));
        var publisher = new OutboxMessagePublisher(outbox, identity, clock);

        using var evento = JsonDocument.Parse("""
            {"protocol_version":"automation-events/1","event_id":"6f1c2b9e-1d2a-4c1b-9a51-0e6f3a2b4c5d","sequence":7,
             "type":"etapa.concluida","occurred_at":"2026-11-09T14:03:21.512Z",
             "payload":{"etapa":"rubricas","item":"5066","situacao":"ok","tarefas":50}}
            """);

        await publisher.EnqueueAsync(PortalMessageTypes.AutomationEvent, evento.RootElement.Clone(),
            executionId: "exe_1", executionAttemptId: "att_1");

        gravado.Should().NotBeNull();
        gravado!.MessageType.Should().Be(PortalMessageTypes.ExecutionEventBatch);
        using var batch = JsonDocument.Parse(gravado.PayloadJson);
        var item = batch.RootElement.GetProperty("events")[0];
        item.GetProperty("event_type").GetString().Should().Be("automation.event");
        item.GetProperty("event_sequence").GetInt64().Should().Be(1);
        var transportado = item.GetProperty("payload");
        transportado.GetProperty("type").GetString().Should().Be("etapa.concluida");
        transportado.GetProperty("sequence").GetInt64().Should().Be(7);
        transportado.GetProperty("payload").GetProperty("tarefas").GetInt32().Should().Be(50);
    }
}
