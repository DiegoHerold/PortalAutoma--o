using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Interactive;
using Biason.AutomationAgent.IntegrationTests.Helpers;
using FluentAssertions;
using Xunit;

namespace Biason.AutomationAgent.IntegrationTests.Interactive;

public sealed class DesktopLockRepositoryTests : IAsyncLifetime
{
    private readonly TestHelper _helper = new();

    public async Task InitializeAsync() => await _helper.InitializeDatabaseAsync();

    public Task DisposeAsync()
    {
        _helper.Dispose();
        return Task.CompletedTask;
    }

    [Fact]
    public async Task TryAcquireAsync_AcquiresAllLocksAtomically()
    {
        var repo = _helper.CreateDesktopLockRepository();
        var now = DateTime.UtcNow;

        var ok = await repo.TryAcquireAsync(new[]
        {
            Lock("windows_desktop", "exec_1", "att_1", now),
            Lock("keyboard", "exec_1", "att_1", now),
            Lock("mouse", "exec_1", "att_1", now)
        }, now);

        ok.Should().BeTrue();
        var locks = await repo.GetByOwnerAsync("exec_1", "att_1");
        locks.Select(l => l.LockKey).Should().BeEquivalentTo("windows_desktop", "keyboard", "mouse");
        locks.Should().OnlyContain(l => l.Status == DesktopLockStatus.Reserved);
    }

    [Fact]
    public async Task TryAcquireAsync_RejectsConflictingActiveLock()
    {
        var repo = _helper.CreateDesktopLockRepository();
        var now = DateTime.UtcNow;

        (await repo.TryAcquireAsync(new[] { Lock("windows_desktop", "exec_1", "att_1", now) }, now)).Should().BeTrue();

        var ok = await repo.TryAcquireAsync(new[] { Lock("windows_desktop", "exec_2", "att_2", now) }, now);

        ok.Should().BeFalse();
        (await repo.GetByOwnerAsync("exec_2", "att_2")).Should().BeEmpty();
    }

    [Fact]
    public async Task ReleaseAsync_AllowsNextOwner()
    {
        var repo = _helper.CreateDesktopLockRepository();
        var now = DateTime.UtcNow;

        (await repo.TryAcquireAsync(new[] { Lock("excel_application", "exec_1", "att_1", now) }, now)).Should().BeTrue();
        await repo.ReleaseAsync("exec_1", "att_1", now.AddSeconds(1));

        var ok = await repo.TryAcquireAsync(new[] { Lock("excel_application", "exec_2", "att_2", now.AddSeconds(2)) }, now.AddSeconds(2));

        ok.Should().BeTrue();
        var locks = await repo.GetByOwnerAsync("exec_2", "att_2");
        locks.Should().ContainSingle(l => l.LockKey == "excel_application");
    }

    [Fact]
    public async Task MarkExpiredAsync_MarksLeaseAsStale()
    {
        var repo = _helper.CreateDesktopLockRepository();
        var now = DateTime.UtcNow;
        var expired = Lock("dominio_application", "exec_1", "att_1", now);
        expired.LeaseExpiresAtUtc = now.AddSeconds(-1);

        (await repo.TryAcquireAsync(new[] { expired }, now.AddSeconds(-2))).Should().BeTrue();
        var recovered = await repo.MarkExpiredAsync(now);

        recovered.Should().Be(1);
        var locks = await repo.GetAllAsync();
        locks.Should().ContainSingle(l => l.LockKey == "dominio_application" && l.Status == DesktopLockStatus.Stale);
    }

    private static ResourceLockRecord Lock(string key, string executionId, string attemptId, DateTime now) => new()
    {
        LockKey = key,
        OwnerExecutionId = executionId,
        OwnerAttemptId = attemptId,
        SessionId = 2,
        CreatedAtUtc = now,
        LeaseExpiresAtUtc = now.AddMinutes(5),
        Status = DesktopLockStatus.Reserved
    };
}
