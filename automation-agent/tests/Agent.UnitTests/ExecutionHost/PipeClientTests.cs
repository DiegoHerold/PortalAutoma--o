using Biason.AutomationAgent.ExecutionHost.Protocol;
using FluentAssertions;
using Xunit;

namespace Biason.AutomationAgent.UnitTests.ExecutionHost;

public sealed class PipeClientTests
{
    [Fact]
    public async Task Constructor_DoesNotWriteToUnconnectedPipe()
    {
        var act = async () =>
        {
            await using var client = new PipeClient($"missing_{Guid.NewGuid():N}", "exe_1", "att_1");
        };

        await act.Should().NotThrowAsync();
    }
}
