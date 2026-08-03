using Biason.AutomationAgent.Protocol.Local;
using FluentAssertions;
using Xunit;

namespace Biason.AutomationAgent.UnitTests.LocalProtocol;

public sealed class LocalExecutionTokenTests
{
    [Fact]
    public void SignedToken_ValidatesExpectedClaims()
    {
        var token = LocalExecutionToken.Issue("session-secret", "exec_1", "att_1", 2, "sr_1", DateTime.UtcNow.AddMinutes(5));

        var ok = LocalExecutionToken.TryValidate(token, "session-secret", "exec_1", "att_1", 2, "sr_1", DateTime.UtcNow, out var errorCode);

        ok.Should().BeTrue();
        errorCode.Should().BeNull();
    }

    [Fact]
    public void SignedToken_RejectsWrongSession()
    {
        var token = LocalExecutionToken.Issue("session-secret", "exec_1", "att_1", 2, "sr_1", DateTime.UtcNow.AddMinutes(5));

        var ok = LocalExecutionToken.TryValidate(token, "session-secret", "exec_1", "att_1", 3, "sr_1", DateTime.UtcNow, out var errorCode);

        ok.Should().BeFalse();
        errorCode.Should().Be("INTERACTIVE_EXECUTION_TOKEN_INVALID");
    }

    [Fact]
    public void SignedToken_RejectsExpiredToken()
    {
        var token = LocalExecutionToken.Issue("session-secret", "exec_1", "att_1", 2, "sr_1", DateTime.UtcNow.AddSeconds(-1));

        var ok = LocalExecutionToken.TryValidate(token, "session-secret", "exec_1", "att_1", 2, "sr_1", DateTime.UtcNow, out var errorCode);

        ok.Should().BeFalse();
        errorCode.Should().Be("INTERACTIVE_EXECUTION_TOKEN_EXPIRED");
    }
}
