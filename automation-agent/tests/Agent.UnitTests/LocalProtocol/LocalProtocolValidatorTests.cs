using Biason.AutomationAgent.Protocol.Local;
using Biason.AutomationAgent.Protocol.Serialization;
using FluentAssertions;
using Xunit;

namespace Biason.AutomationAgent.UnitTests.LocalProtocol;

public sealed class LocalProtocolValidatorTests
{
    [Fact]
    public void ValidEnvelope_IsAccepted()
    {
        var now = DateTime.UtcNow;
        var json = ProtocolJson.Serialize(new LocalProtocolEnvelope
        {
            MessageType = LocalMessageTypes.Heartbeat,
            SentAt = now,
            SessionRunnerInstanceId = "sr_test",
            SessionId = 2,
            Payload = new { ok = true }
        });

        var (result, envelope) = LocalProtocolValidator.Parse(json, now, 1024 * 1024);

        result.IsValid.Should().BeTrue();
        envelope!.MessageType.Should().Be(LocalMessageTypes.Heartbeat);
    }

    [Fact]
    public void OversizedEnvelope_IsRejected()
    {
        var json = ProtocolJson.Serialize(new LocalProtocolEnvelope
        {
            MessageType = LocalMessageTypes.Heartbeat,
            Payload = new { value = new string('x', 256) }
        });

        var (result, envelope) = LocalProtocolValidator.Parse(json, DateTime.UtcNow, 32);

        result.IsValid.Should().BeFalse();
        result.ErrorCode.Should().Be(LocalProtocolErrors.MessageTooLarge);
        envelope.Should().BeNull();
    }

    [Fact]
    public void VersionMismatch_IsRejected()
    {
        var json = ProtocolJson.Serialize(new LocalProtocolEnvelope
        {
            ProtocolVersion = "1.1",
            MessageType = LocalMessageTypes.Hello
        });

        var (result, _) = LocalProtocolValidator.Parse(json, DateTime.UtcNow, 1024 * 1024, expectedVersion: "1.0");

        result.IsValid.Should().BeFalse();
        result.ErrorCode.Should().Be(LocalProtocolErrors.UnsupportedProtocolVersion);
    }

    [Fact]
    public void ChallengeResponse_IsDeterministicAndBoundToProcess()
    {
        var first = LocalAuthentication.ChallengeResponse("nonce", "sr_1", 2, 10);
        var second = LocalAuthentication.ChallengeResponse("nonce", "sr_1", 2, 10);
        var otherPid = LocalAuthentication.ChallengeResponse("nonce", "sr_1", 2, 11);

        first.Should().Be(second);
        first.Should().NotBe(otherPid);
    }
}
