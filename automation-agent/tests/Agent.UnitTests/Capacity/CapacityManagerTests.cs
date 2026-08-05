using Biason.AutomationAgent.Application.Capacity;
using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Capacity;
using FluentAssertions;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using NSubstitute;
using Xunit;

namespace Biason.AutomationAgent.UnitTests.Capacity;

public class CapacityManagerTests
{
    private readonly CapacityManager _sut;
    private readonly IReservationRepository _reservations;

    public CapacityManagerTests()
    {
        var options = Options.Create(new CapacityOptions
        {
            BackgroundPoolSize = 3,
            BrowserPoolSize = 1,
            InteractivePoolSize = 0,
            SnapshotTtlSeconds = 60
        });
        var identity = Substitute.For<IAgentIdentityService>();
        var clock = Substitute.For<IClock>();
        clock.UtcNow.Returns(DateTime.UtcNow);
        _reservations = Substitute.For<IReservationRepository>();
        _reservations.GetActiveAsync(Arg.Any<CancellationToken>())
            .Returns(Task.FromResult<IReadOnlyList<ResourceReservation>>(Array.Empty<ResourceReservation>()));
        var logger = Substitute.For<ILogger<CapacityManager>>();

        _sut = new CapacityManager(options, identity, clock, _reservations, logger);
    }

    [Fact]
    public void GetSnapshot_ReturnsAllPools()
    {
        var snapshot = _sut.GetSnapshot();

        snapshot.Pools.Should().ContainKey(PoolType.Background);
        snapshot.Pools.Should().ContainKey(PoolType.Browser);
        snapshot.Pools.Should().ContainKey(PoolType.Interactive);
    }

    [Fact]
    public void GetPoolCapacity_ReturnsCorrectCounts()
    {
        var bg = _sut.GetPoolCapacity(PoolType.Background);

        bg.EffectiveTotal.Should().Be(3);
        bg.Used.Should().Be(0);
        bg.Available.Should().Be(3);
    }

    [Fact]
    public void HasAvailableSlots_WhenEmpty_ReturnsTrue()
    {
        _sut.HasAvailableSlots(PoolType.Background, 1).Should().BeTrue();
    }

    [Fact]
    public void HasAvailableSlots_WhenFull_ReturnsFalse()
    {
        _sut.IncrementUsed(PoolType.Background);
        _sut.IncrementUsed(PoolType.Background);
        _sut.IncrementUsed(PoolType.Background);

        _sut.HasAvailableSlots(PoolType.Background, 1).Should().BeFalse();
    }

    [Fact]
    public void IncrementDecrement_TracksUsage()
    {
        _sut.IncrementUsed(PoolType.Browser);
        _sut.GetPoolCapacity(PoolType.Browser).Used.Should().Be(1);

        _sut.DecrementUsed(PoolType.Browser);
        _sut.GetPoolCapacity(PoolType.Browser).Used.Should().Be(0);
    }

    [Fact]
    public void InteractivePool_HasZeroCapacity()
    {
        var interactive = _sut.GetPoolCapacity(PoolType.Interactive);
        interactive.EffectiveTotal.Should().Be(0);
        _sut.HasAvailableSlots(PoolType.Interactive, 1).Should().BeFalse();
    }
}
