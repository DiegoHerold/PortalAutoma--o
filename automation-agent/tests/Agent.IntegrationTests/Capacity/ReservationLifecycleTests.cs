using Biason.AutomationAgent.Application.Capacity;
using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models;
using Biason.AutomationAgent.Domain.Models.Capacity;
using Biason.AutomationAgent.Infrastructure.Persistence;
using Biason.AutomationAgent.IntegrationTests.Helpers;
using FluentAssertions;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.Extensions.Options;
using NSubstitute;
using Xunit;

namespace Biason.AutomationAgent.IntegrationTests.Capacity;

/// <summary>
/// Bloco 5.5, seções 8-12 e 48 ("Reservations"): lifecycle
/// TEMPORARY -&gt; COMMITTED/RELEASED/EXPIRED, consumo de capacidade,
/// expiração periódica e reidratação do CapacityManager após restart.
/// </summary>
public sealed class ReservationLifecycleTests : IAsyncLifetime
{
    private readonly TestHelper _helper = new();

    public async Task InitializeAsync() => await _helper.InitializeDatabaseAsync();

    public Task DisposeAsync()
    {
        _helper.Dispose();
        return Task.CompletedTask;
    }

    // === temporary-reservation + reservation-capacity-consumed ===

    [Fact]
    public async Task ReserveAsync_CreatesTemporaryReservation_AndConsumesCapacityImmediately()
    {
        var repo = _helper.CreateReservationRepository();
        var capacity = CreateCapacityManager(repo, backgroundSlots: 2);
        var manager = CreateReservationManager(repo, capacity);

        var reservation = await ReserveSeededAsync(manager, "exec_1");

        reservation.Status.Should().Be(ReservationStatus.Temporary);
        capacity.GetPoolCapacity(PoolType.Background).Reserved.Should().Be(1);
        capacity.GetPoolCapacity(PoolType.Background).Available.Should().Be(1);
    }

    // === commit ===

    [Fact]
    public async Task TryCommitAsync_TransitionsTemporaryToCommitted()
    {
        var repo = _helper.CreateReservationRepository();
        var capacity = CreateCapacityManager(repo, backgroundSlots: 2);
        var manager = CreateReservationManager(repo, capacity);

        var reservation = await ReserveSeededAsync(manager, "exec_2");
        var committed = await manager.TryCommitAsync(reservation.ReservationId);

        committed.Should().NotBeNull();
        committed!.Status.Should().Be(ReservationStatus.Committed);

        // Committed continua consumindo capacidade (só Release/Expire liberam).
        capacity.GetPoolCapacity(PoolType.Background).Reserved.Should().Be(1);
    }

    [Fact]
    public async Task TryCommitAsync_IsIdempotent_WhenAlreadyCommitted()
    {
        var repo = _helper.CreateReservationRepository();
        var capacity = CreateCapacityManager(repo, backgroundSlots: 2);
        var manager = CreateReservationManager(repo, capacity);

        var reservation = await ReserveSeededAsync(manager, "exec_2b");
        await manager.TryCommitAsync(reservation.ReservationId);

        var secondAttempt = await manager.TryCommitAsync(reservation.ReservationId);

        secondAttempt.Should().NotBeNull();
        secondAttempt!.Status.Should().Be(ReservationStatus.Committed);
        // Não deve consumir capacidade uma segunda vez.
        capacity.GetPoolCapacity(PoolType.Background).Reserved.Should().Be(1);
    }

    // === reservation-expiration + commit-expiration-race ===

    [Fact]
    public async Task TryCommitAsync_OnExpiredReservation_ReturnsExpiredAndReleasesCapacity()
    {
        var repo = _helper.CreateReservationRepository();
        var capacity = CreateCapacityManager(repo, backgroundSlots: 2);
        var clock = new ManualClock(DateTime.UtcNow);
        var manager = CreateReservationManager(repo, capacity, clock, reservationTimeoutSeconds: 60);

        var reservation = await ReserveSeededAsync(manager, "exec_3");

        // Avança o relógio para além do TTL (60s) sem que ninguém tenha
        // chamado ExpireStaleAsync ainda — simula o commit chegando tarde
        // (commit tardio, seção 16 / race commit-vs-expiração, seção 15).
        clock.Advance(TimeSpan.FromSeconds(61));

        var result = await manager.TryCommitAsync(reservation.ReservationId);

        result.Should().NotBeNull();
        result!.Status.Should().Be(ReservationStatus.Expired);
        capacity.GetPoolCapacity(PoolType.Background).Reserved.Should().Be(0);
    }

    [Fact]
    public async Task ExpireStaleAsync_ReleasesCapacity_ForTemporaryReservationsPastTtl()
    {
        var repo = _helper.CreateReservationRepository();
        var capacity = CreateCapacityManager(repo, backgroundSlots: 2);
        var clock = new ManualClock(DateTime.UtcNow);
        var manager = CreateReservationManager(repo, capacity, clock, reservationTimeoutSeconds: 60);

        var reservation = await ReserveSeededAsync(manager, "exec_4");
        capacity.GetPoolCapacity(PoolType.Background).Reserved.Should().Be(1);

        clock.Advance(TimeSpan.FromSeconds(61));
        await manager.ExpireStaleAsync();

        capacity.GetPoolCapacity(PoolType.Background).Reserved.Should().Be(0);
        var reloaded = await manager.GetAsync(reservation.ReservationId);
        reloaded!.Status.Should().Be(ReservationStatus.Expired);
    }

    [Fact]
    public async Task ExpireStaleAsync_DoesNotExpireCommittedReservations()
    {
        var repo = _helper.CreateReservationRepository();
        var capacity = CreateCapacityManager(repo, backgroundSlots: 2);
        var clock = new ManualClock(DateTime.UtcNow);
        var manager = CreateReservationManager(repo, capacity, clock, reservationTimeoutSeconds: 60);

        var reservation = await ReserveSeededAsync(manager, "exec_5");
        await manager.TryCommitAsync(reservation.ReservationId);

        clock.Advance(TimeSpan.FromSeconds(61));
        await manager.ExpireStaleAsync();

        var reloaded = await manager.GetAsync(reservation.ReservationId);
        reloaded!.Status.Should().Be(ReservationStatus.Committed);
        capacity.GetPoolCapacity(PoolType.Background).Reserved.Should().Be(1);
    }

    // === release-on-failure ===

    [Fact]
    public async Task ReleaseAsync_ReleasesFromEitherTemporaryOrCommitted()
    {
        var repo = _helper.CreateReservationRepository();
        var capacity = CreateCapacityManager(repo, backgroundSlots: 2);
        var manager = CreateReservationManager(repo, capacity);

        var temp = await ReserveSeededAsync(manager, "exec_6");
        await manager.ReleaseAsync(temp.ReservationId);
        capacity.GetPoolCapacity(PoolType.Background).Reserved.Should().Be(0);

        var committed = await ReserveSeededAsync(manager, "exec_7");
        await manager.TryCommitAsync(committed.ReservationId);
        await manager.ReleaseAsync(committed.ReservationId);
        capacity.GetPoolCapacity(PoolType.Background).Reserved.Should().Be(0);

        (await manager.GetAsync(temp.ReservationId))!.Status.Should().Be(ReservationStatus.Released);
        (await manager.GetAsync(committed.ReservationId))!.Status.Should().Be(ReservationStatus.Released);
    }

    // === reservation-rehydrate + capacity-restart-bug ===

    [Fact]
    public async Task RehydrateReservationsAsync_RestoresReservedCapacity_AfterSimulatedRestart()
    {
        var repo = _helper.CreateReservationRepository();
        var firstInstanceCapacity = CreateCapacityManager(repo, backgroundSlots: 3);
        var manager = CreateReservationManager(repo, firstInstanceCapacity);

        var temp = await ReserveSeededAsync(manager, "exec_8");
        var committed = await ReserveSeededAsync(manager, "exec_9");
        await manager.TryCommitAsync(committed.ReservationId);

        firstInstanceCapacity.GetPoolCapacity(PoolType.Background).Reserved.Should().Be(2);

        // Simula um restart: nova instância de CapacityManager, começa zerada.
        var restartedCapacity = CreateCapacityManager(repo, backgroundSlots: 3);
        restartedCapacity.GetPoolCapacity(PoolType.Background).Reserved.Should().Be(0);

        // Sem rehydrate, o Agent aceitaria até 3 novas execuções mesmo com 2
        // reservas ainda válidas no SQLite — over-admission (Bloco 5.5, seção 12).
        await restartedCapacity.RehydrateReservationsAsync();

        restartedCapacity.GetPoolCapacity(PoolType.Background).Reserved.Should().Be(2);
        restartedCapacity.GetPoolCapacity(PoolType.Background).Available.Should().Be(1);
        restartedCapacity.HasAvailableSlots(PoolType.Background, 2).Should().BeFalse();

        // Confirma que a reserva Temporary (não commitada) também contou —
        // rehydrate cobre os dois estados que consomem capacidade.
        (await manager.GetAsync(temp.ReservationId))!.Status.Should().Be(ReservationStatus.Temporary);
    }

    private static CapacityManager CreateCapacityManager(IReservationRepository repo, int backgroundSlots)
    {
        var options = Options.Create(new CapacityOptions
        {
            BackgroundPoolSize = backgroundSlots,
            BrowserPoolSize = 1,
            InteractivePoolSize = 1,
            SnapshotTtlSeconds = 60
        });
        var identity = Substitute.For<IAgentIdentityService>();
        return new CapacityManager(options, identity, new Biason.AutomationAgent.Infrastructure.Clock.SystemClock(), repo, NullLogger<CapacityManager>.Instance);
    }

    private ResourceReservationManager CreateReservationManager(
        IReservationRepository repo,
        ICapacityManager capacity,
        IClock? clock = null,
        int reservationTimeoutSeconds = 300)
    {
        var execOptions = Options.Create(new ExecutionOptions
        {
            ReservationTimeoutSeconds = reservationTimeoutSeconds
        });

        return new ResourceReservationManager(repo, capacity, clock ?? _helper.Clock, execOptions, NullLogger<ResourceReservationManager>.Instance);
    }

    private async Task<ResourceReservation> ReserveSeededAsync(
        ResourceReservationManager manager,
        string executionId,
        PoolType pool = PoolType.Background,
        int slots = 1)
    {
        await SeedExecutionAsync(executionId, pool);
        return await manager.ReserveAsync(executionId, pool, slots);
    }

    private async Task SeedExecutionAsync(string executionId, PoolType pool)
    {
        var executionRepo = new ExecutionRepository(_helper.DbManager);
        await executionRepo.SaveAsync(new ExecutionRecord
        {
            ExecutionId = executionId,
            CurrentState = ExecutionState.Offered,
            CreatedAtUtc = _helper.Clock.UtcNow,
            LastTransitionUtc = _helper.Clock.UtcNow,
            AutomationId = "test.automation",
            AutomationVersionId = "pkg_test",
            Pool = pool,
            CurrentAttemptId = $"att_{executionId}"
        });
    }

    /// <summary>
    /// Clock de teste com UtcNow ajustável manualmente — permite simular o
    /// tempo passando (reserva vencendo o TTL) sem Thread.Sleep. Precisa ser
    /// a mesma instância usada tanto na criação da reserva (ExpiresAtUtc)
    /// quanto na checagem posterior (TryCommitAsync/ExpireStaleAsync).
    /// </summary>
    private sealed class ManualClock : IClock
    {
        private DateTime _now;

        public ManualClock(DateTime initialUtcNow) => _now = initialUtcNow;

        public DateTime UtcNow => _now;

        public void Advance(TimeSpan by) => _now = _now.Add(by);
    }
}
