using Biason.AutomationAgent.Protocol.Envelope;
using Biason.AutomationAgent.Protocol.Messages;
using Biason.AutomationAgent.Protocol.Serialization;
using Biason.AutomationAgent.Protocol.Validation;
using FluentAssertions;
using Xunit;

namespace Biason.AutomationAgent.UnitTests.Protocol;

public sealed class EnvelopeValidatorTests
{
    private static readonly DateTime Now = new(2026, 7, 31, 12, 0, 0, DateTimeKind.Utc);

    private static string BuildRaw(
        string messageType = PortalMessageTypes.ExecutionOffer,
        string protocolVersion = "1.0",
        string? messageId = "msg_abc123",
        DateTime? sentAt = null,
        string? agentId = "agt_123",
        object? payload = null)
    {
        var envelope = new ProtocolEnvelope
        {
            ProtocolVersion = protocolVersion,
            MessageId = messageId!,
            MessageType = messageType,
            SentAt = sentAt ?? Now,
            AgentId = agentId,
            Payload = payload ?? new { }
        };
        return ProtocolJson.Serialize(envelope);
    }

    [Fact]
    public void ValidOffer_IsAccepted()
    {
        var (result, envelope) = EnvelopeValidator.ParseInbound(BuildRaw(), Now);

        result.IsValid.Should().BeTrue();
        envelope.Should().NotBeNull();
        envelope!.MessageType.Should().Be(PortalMessageTypes.ExecutionOffer);
    }

    // protocol-version-mismatch
    [Theory]
    [InlineData("2.0")]
    [InlineData("3.1")]
    [InlineData("abc")]
    public void IncompatibleProtocolVersion_IsRejected(string version)
    {
        var (result, envelope) = EnvelopeValidator.ParseInbound(BuildRaw(protocolVersion: version), Now);

        result.IsValid.Should().BeFalse();
        result.ErrorCode.Should().Be(ProtocolErrorCodes.UnsupportedProtocolVersion);
        envelope.Should().BeNull();
    }

    [Fact]
    public void MinorVersionBump_RemainsCompatible()
    {
        // Compatibilidade por major: 1.7 é aceito por um Agent 1.0.
        var (result, _) = EnvelopeValidator.ParseInbound(BuildRaw(protocolVersion: "1.7"), Now);
        result.IsValid.Should().BeTrue();
    }

    [Fact]
    public void MissingMessageId_IsRejected()
    {
        var raw = """
            {"protocol_version":"1.0","message_type":"execution.offer","sent_at":"2026-07-31T12:00:00Z"}
            """;

        var (result, _) = EnvelopeValidator.ParseInbound(raw, Now);

        result.IsValid.Should().BeFalse();
        result.ErrorCode.Should().Be(ProtocolErrorCodes.MissingMessageId);
    }

    // invalid-schema
    [Fact]
    public void MalformedJson_IsRejected()
    {
        var (result, _) = EnvelopeValidator.ParseInbound("{ not json", Now);

        result.IsValid.Should().BeFalse();
        result.ErrorCode.Should().Be(ProtocolErrorCodes.MalformedJson);
    }

    [Fact]
    public void UnknownMessageType_IsRejected()
    {
        var (result, _) = EnvelopeValidator.ParseInbound(BuildRaw(messageType: "execution.do_whatever"), Now);

        result.IsValid.Should().BeFalse();
        result.ErrorCode.Should().Be(ProtocolErrorCodes.UnknownMessageType);
    }

    [Fact]
    public void OutboundOnlyMessageType_FromPortal_IsRejected()
    {
        // execution.accept é do Agent para o Portal; o inverso não faz sentido.
        var (result, _) = EnvelopeValidator.ParseInbound(BuildRaw(messageType: PortalMessageTypes.ExecutionAccept), Now);

        result.IsValid.Should().BeFalse();
        result.ErrorCode.Should().Be(ProtocolErrorCodes.UnexpectedDirection);
    }

    // oversized-message
    [Fact]
    public void OversizedMessage_IsRejected()
    {
        var hugePayload = new { blob = new string('x', ProtocolConstants.MaxMessageSizeBytes + 1024) };
        var raw = BuildRaw(payload: hugePayload);

        var (result, _) = EnvelopeValidator.ParseInbound(raw, Now);

        result.IsValid.Should().BeFalse();
        result.ErrorCode.Should().Be(ProtocolErrorCodes.PayloadTooLarge);
    }

    [Fact]
    public void ExcessiveClockSkew_IsRejected()
    {
        var skewed = Now.AddMinutes(30);
        var (result, _) = EnvelopeValidator.ParseInbound(BuildRaw(sentAt: skewed), Now);

        result.IsValid.Should().BeFalse();
        result.ErrorCode.Should().Be(ProtocolErrorCodes.ClockSkewTooLarge);
    }

    [Fact]
    public void MessageForAnotherAgent_IsRejected()
    {
        var (result, _) = EnvelopeValidator.ParseInbound(
            BuildRaw(agentId: "agt_outro"), Now, expectedAgentId: "agt_123");

        result.IsValid.Should().BeFalse();
        result.ErrorCode.Should().Be(ProtocolErrorCodes.AgentMismatch);
    }

    [Fact]
    public void OutboundSerialization_RejectsOversizedPayload()
    {
        var envelope = ProtocolEnvelope.Create(
            PortalMessageTypes.ExecutionLog,
            new { message = new string('y', ProtocolConstants.MaxMessageSizeBytes + 1024) });

        var ok = EnvelopeValidator.TrySerializeOutbound(envelope, out _, out var error);

        ok.Should().BeFalse();
        error.Should().Contain("HTTPS");
    }

    [Fact]
    public void OptionalFields_AreOmittedFromWire()
    {
        var envelope = ProtocolEnvelope.Create(PortalMessageTypes.Heartbeat, new { ok = true });
        var json = ProtocolJson.Serialize(envelope);

        json.Should().NotContain("execution_id");
        json.Should().NotContain("sequence");
        json.Should().Contain("protocol_version");
        json.Should().Contain("message_id");
    }

    [Fact]
    public void MessageIds_AreUnique()
    {
        var ids = Enumerable.Range(0, 1000).Select(_ => ProtocolEnvelope.NewMessageId()).ToHashSet();
        ids.Should().HaveCount(1000);
    }

    [Fact]
    public void CommandTypes_AreSubsetOfInbound()
    {
        // Todo comando precisa ser recebível; caso contrário a Inbox nunca o veria.
        PortalMessageTypes.Commands.Should().BeSubsetOf(PortalMessageTypes.Inbound);
    }
}
