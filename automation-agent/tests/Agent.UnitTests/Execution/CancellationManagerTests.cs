using Biason.AutomationAgent.Application.Execution;
using FluentAssertions;
using Microsoft.Extensions.Logging;
using NSubstitute;
using Xunit;

namespace Biason.AutomationAgent.UnitTests.Execution;

public class CancellationManagerTests
{
    private readonly CancellationManager _sut;

    public CancellationManagerTests()
    {
        var logger = Substitute.For<ILogger<CancellationManager>>();
        _sut = new CancellationManager(logger);
    }

    [Fact]
    public void CreateLinked_ReturnsLinkedToken()
    {
        using var parentCts = new CancellationTokenSource();
        using var cts = _sut.CreateLinked("exec_1", 300, parentCts.Token);

        cts.Should().NotBeNull();
        cts.Token.IsCancellationRequested.Should().BeFalse();
    }

    [Fact]
    public void CreateLinked_CancelsOnParentCancel()
    {
        using var parentCts = new CancellationTokenSource();
        using var cts = _sut.CreateLinked("exec_2", 300, parentCts.Token);

        parentCts.Cancel();
        cts.Token.IsCancellationRequested.Should().BeTrue();
    }

    [Fact]
    public async Task RequestCancellation_CancelsToken()
    {
        using var parentCts = new CancellationTokenSource();
        using var cts = _sut.CreateLinked("exec_3", 300, parentCts.Token);

        await _sut.RequestCancellationAsync("exec_3");

        cts.Token.IsCancellationRequested.Should().BeTrue();
    }

    [Fact]
    public async Task Remove_DisposesSource()
    {
        using var parentCts = new CancellationTokenSource();
        var cts = _sut.CreateLinked("exec_4", 300, parentCts.Token);

        _sut.Remove("exec_4");

        // After removal, requesting cancellation should not throw (but source is disposed).
        // RequestCancellationAsync retorna Task: precisa de NotThrowAsync, não NotThrow
        // (que só existe para Action síncrona).
        var act = () => _sut.RequestCancellationAsync("exec_4");
        await act.Should().NotThrowAsync();
    }

    [Fact]
    public async Task CreateLinked_TimesOutAfterTimeout()
    {
        using var parentCts = new CancellationTokenSource();
        using var cts = _sut.CreateLinked("exec_5", 1, parentCts.Token);

        await Task.Delay(1500);
        cts.Token.IsCancellationRequested.Should().BeTrue();
    }
}
