using Biason.AutomationAgent.Application.Sessions;
using FluentAssertions;
using Xunit;

namespace Biason.AutomationAgent.UnitTests.Sessions;

public sealed class InteractiveExecutionTokenServiceTests
{
    [Fact]
    public void IssuedToken_ValidatesOnlyForBoundExecutionSessionAndRunner()
    {
        var service = new InteractiveExecutionTokenService();
        var token = service.Issue("exec_1", "att_1", 2, "sr_1", DateTime.UtcNow.AddMinutes(10));

        service.Validate(token.Token, "exec_1", "att_1", 2, "sr_1", DateTime.UtcNow).Should().BeTrue();
        service.Validate(token.Token, "exec_1", "att_2", 2, "sr_1", DateTime.UtcNow).Should().BeFalse();
        service.Validate(token.Token, "exec_1", "att_1", 3, "sr_1", DateTime.UtcNow).Should().BeFalse();
    }

    [Fact]
    public void ExpiredToken_IsRejected()
    {
        var service = new InteractiveExecutionTokenService();
        var token = service.Issue("exec_1", "att_1", 2, "sr_1", DateTime.UtcNow.AddSeconds(-1));

        service.Validate(token.Token, "exec_1", "att_1", 2, "sr_1", DateTime.UtcNow).Should().BeFalse();
    }
}
