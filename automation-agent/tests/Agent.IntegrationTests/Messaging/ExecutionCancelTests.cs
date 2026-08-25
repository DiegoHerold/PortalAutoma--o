using Biason.AutomationAgent.Application.Capacity;
using Biason.AutomationAgent.Application.Messaging;
using Biason.AutomationAgent.Application.Messaging.Handlers;
using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models;
using Biason.AutomationAgent.Domain.Models.Capacity;
using Biason.AutomationAgent.Domain.Models.Messaging;
using Biason.AutomationAgent.Infrastructure.Persistence;
using Biason.AutomationAgent.IntegrationTests.Helpers;
using Biason.AutomationAgent.Protocol.Messages;
using Biason.AutomationAgent.Protocol.Serialization;
using FluentAssertions;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.Extensions.Options;
using NSubstitute;
using Xunit;

namespace Biason.AutomationAgent.IntegrationTests.Messaging;

/// <summary>
/// Bloco 5.5, seção 20 — execution.cancel_requested (Incremento 4).
/// Constrói os ExecutionRecord diretamente no repositório (em vez de passar
/// por ExecutionOfferHandler/ExecutionCommitHandler) para isolar a lógica do
/// ExecutionCancelRequestedHandler dos demais handlers, que já têm sua
/// própria cobertura em ExecutionOfferAndCommitTests.
/// </summary>
public sealed class ExecutionCancelTests : IAsyncLifetime
{
    private readonly TestHelper _helper = new();

    public async Task InitializeAsync()
    {
        await _helper.InitializeDatabaseAsync();
        await _helper.SeedRegisteredAgentAsync(agentId: "agt_cancel", credentialValue: "segredo-teste");
    }

    public Task DisposeAsync()
    {
        _helper.Dispose();
        return Task.CompletedTask;
    }

    [Fact]
    public async Task Cancel_ReservedExecution_TransitionsToCancelled_ReleasesReservation_SendsCancelled()
    {
        var fx = CreateFixture();
        var reservation = await SeedExecutionWithReservationAsync(
            fx, "exec_cancel_reserved", "att_cancel_reserved", ExecutionState.Reserved);

        var command = BuildCancelCommand("exec_cancel_reserved", "att_cancel_reserved", "Portal cancelled the run");
        var result = await fx.Handler.HandleAsync(command);

        result.Success.Should().BeTrue();
        result.Result.Should().Be("cancelled");

        var execution = await fx.ExecutionRepo.GetAsync("exec_cancel_reserved");
        execution!.CurrentState.Should().Be(ExecutionState.Cancelled);

        var active = await fx.ReservationRepo.GetActiveAsync();
        active.Should().NotContain(r => r.ReservationId == reservation.ReservationId);

        var cancelled = fx.Outbox.Sent.Should().ContainSingle(m => m.MessageType == PortalMessageTypes.ExecutionCancelled).Which;
        using var cancelledJson = System.Text.Json.JsonDocument.Parse(cancelled.PayloadJson);
        cancelledJson.RootElement.GetProperty("execution_id").GetString().Should().Be("exec_cancel_reserved");

        await fx.ExecutionManager.Received(1).CancelAsync("exec_cancel_reserved", Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task Cancel_PreparingExecution_TransitionsToCancelled_ReleasesReservation()
    {
        var fx = CreateFixture();
        var reservation = await SeedExecutionWithReservationAsync(
            fx, "exec_cancel_preparing", "att_cancel_preparing", ExecutionState.Preparing);

        var command = BuildCancelCommand("exec_cancel_preparing", "att_cancel_preparing", "duplicate execution");
        var result = await fx.Handler.HandleAsync(command);

        result.Result.Should().Be("cancelled");
        var execution = await fx.ExecutionRepo.GetAsync("exec_cancel_preparing");
        execution!.CurrentState.Should().Be(ExecutionState.Cancelled);

        var active = await fx.ReservationRepo.GetActiveAsync();
        active.Should().NotContain(r => r.ReservationId == reservation.ReservationId);
    }

    [Fact]
    public async Task Cancel_TerminalExecution_IsIgnored_NoOutboundMessage()
    {
        var fx = CreateFixture();
        await SeedExecutionAsync(fx, "exec_cancel_terminal", "att_cancel_terminal", ExecutionState.Succeeded, reservationId: null);

        var command = BuildCancelCommand("exec_cancel_terminal", "att_cancel_terminal", "too late");
        var result = await fx.Handler.HandleAsync(command);

        result.Success.Should().BeTrue();
        result.Result.Should().Be("cancel_ignored_already_Succeeded");

        fx.Outbox.Sent.Should().BeEmpty();
        await fx.ExecutionManager.DidNotReceive().CancelAsync(Arg.Any<string>(), Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task Cancel_AlreadyCancelling_DoesNotReemitTelemetry_AndSignalsExecutionManagerAgain()
    {
        var fx = CreateFixture();
        await SeedExecutionAsync(fx, "exec_cancel_inflight", "att_cancel_inflight", ExecutionState.Cancelling, reservationId: null);

        var command = BuildCancelCommand("exec_cancel_inflight", "att_cancel_inflight", "retry from portal");
        var result = await fx.Handler.HandleAsync(command);

        result.Result.Should().Be("cancel_already_in_progress");
        fx.Outbox.Sent.Should().BeEmpty();

        // Estado não deveria ser alterado por este ramo (Cancelling->Cancelled
        // é responsabilidade do ExecutionManager, não deste handler).
        var execution = await fx.ExecutionRepo.GetAsync("exec_cancel_inflight");
        execution!.CurrentState.Should().Be(ExecutionState.Cancelling);

        await fx.ExecutionManager.Received(1).CancelAsync("exec_cancel_inflight", Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task Cancel_UnknownExecution_IsDeadLettered()
    {
        var fx = CreateFixture();
        var command = BuildCancelCommand("exec_does_not_exist", "att_x", "n/a");

        var result = await fx.Handler.HandleAsync(command);

        result.Success.Should().BeFalse();
        result.DeadLetter.Should().BeTrue();
        result.Error.Should().Be("EXECUTION_NOT_FOUND");
    }

    [Fact]
    public async Task Cancel_RunningExecution_DoesNotEmitIntermediateTelemetry_DoesNotMutateExecutionRecord_SignalsExecutionManager()
    {
        var fx = CreateFixture();
        await SeedExecutionAsync(fx, "exec_cancel_running", "att_cancel_running", ExecutionState.Running, reservationId: null);

        var command = BuildCancelCommand("exec_cancel_running", "att_cancel_running", "user requested stop");
        var result = await fx.Handler.HandleAsync(command);

        result.Result.Should().Be("cancel_requested_running");
        // Nenhum evento intermediario aqui: o command ack pertence ao InboxCommandProcessor
        // e o terminal execution.cancelled pertence ao ExecutionManager em voo.
        fx.Outbox.Sent.Should().BeEmpty();

        // O handler não deve ter tocado no ExecutionRecord: a cópia em
        // memória que ExecutionManager.ExecuteAsync mantém é outra instância,
        // e é ela quem vai efetivamente transicionar Running->CancelRequested
        // ->Cancelling->Cancelled quando observar o token cancelado.
        var execution = await fx.ExecutionRepo.GetAsync("exec_cancel_running");
        execution!.CurrentState.Should().Be(ExecutionState.Running);

        await fx.ExecutionManager.Received(1).CancelAsync("exec_cancel_running", Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task Cancel_OfferedExecution_IsDeadLetteredAsTransient()
    {
        var fx = CreateFixture();
        await SeedExecutionAsync(fx, "exec_cancel_offered", "att_cancel_offered", ExecutionState.Offered, reservationId: null);

        var command = BuildCancelCommand("exec_cancel_offered", "att_cancel_offered", "race");
        var result = await fx.Handler.HandleAsync(command);

        result.DeadLetter.Should().BeTrue();
        result.Error.Should().Be("EXECUTION_STATE_TRANSIENT");
    }

    private static InboxCommand BuildCancelCommand(string executionId, string attemptId, string reason, string? messageId = null)
    {
        var payload = new ExecutionCancelRequestedPayload
        {
            ExecutionAttemptId = attemptId,
            Reason = reason
        };

        return new InboxCommand
        {
            Id = Random.Shared.Next(1, int.MaxValue),
            MessageId = messageId ?? $"msg_cancel_{Guid.NewGuid():N}",
            CommandType = PortalMessageTypes.ExecutionCancelRequested,
            PayloadJson = ProtocolJson.Serialize(payload),
            ExecutionId = executionId,
            ExecutionAttemptId = attemptId,
            ReceivedAtUtc = DateTime.UtcNow,
            Status = InboxCommandStatus.Processing
        };
    }

    private static async Task SeedExecutionAsync(
        TestFixture fx, string executionId, string attemptId, ExecutionState state, string? reservationId)
    {
        await fx.ExecutionRepo.SaveAsync(new ExecutionRecord
        {
            ExecutionId = executionId,
            CurrentState = state,
            CreatedAtUtc = DateTime.UtcNow,
            LastTransitionUtc = DateTime.UtcNow,
            AutomationId = "test.automation",
            AutomationVersionId = "pkg_test",
            Pool = PoolType.Background,
            CurrentAttemptId = attemptId,
            ReservationId = reservationId
        });
    }

    private static async Task<ResourceReservation> SeedExecutionWithReservationAsync(
        TestFixture fx, string executionId, string attemptId, ExecutionState state)
    {
        await SeedExecutionAsync(fx, executionId, attemptId, state, reservationId: null);

        var reservation = await fx.Reservations.ReserveAsync(executionId, PoolType.Background, 1);
        var execution = await fx.ExecutionRepo.GetAsync(executionId);
        execution!.ReservationId = reservation.ReservationId;
        await fx.ExecutionRepo.UpdateStateAsync(executionId, execution);

        return reservation;
    }

    private TestFixture CreateFixture(int backgroundSlots = 5)
    {
        var executionRepo = new ExecutionRepository(_helper.DbManager);
        var reservationRepo = new ReservationRepository(_helper.DbManager);
        var identity = Substitute.For<IAgentIdentityService>();
        var clock = new ManualClock(DateTime.UtcNow);

        var capacityOptions = Options.Create(new CapacityOptions
        {
            BackgroundPoolSize = backgroundSlots,
            BrowserPoolSize = 2,
            InteractivePoolSize = 1,
            SnapshotTtlSeconds = 60
        });
        var capacity = new CapacityManager(capacityOptions, identity, clock, reservationRepo, NullLogger<CapacityManager>.Instance);

        var execOptions = Options.Create(new ExecutionOptions { ReservationTimeoutSeconds = 300 });
        var reservations = new ResourceReservationManager(reservationRepo, capacity, clock, execOptions, NullLogger<ResourceReservationManager>.Instance);

        var outboxRepo = _helper.CreateOutboxRepository();
        var outboxPublisher = new OutboxMessagePublisher(outboxRepo, _helper.CreateIdentityRepository(), clock);
        var outboxSpy = new OutboxSpy(outboxRepo);

        var executionManager = Substitute.For<IExecutionManager>();

        var handler = new ExecutionCancelRequestedHandler(
            executionRepo, reservations, executionManager, outboxPublisher, clock,
            NullLogger<ExecutionCancelRequestedHandler>.Instance, desktopLocks: null);

        return new TestFixture(handler, executionRepo, reservationRepo, reservations, outboxSpy, executionManager);
    }

    private sealed record TestFixture(
        ExecutionCancelRequestedHandler Handler,
        ExecutionRepository ExecutionRepo,
        ReservationRepository ReservationRepo,
        ResourceReservationManager Reservations,
        OutboxSpy Outbox,
        IExecutionManager ExecutionManager);

    private sealed class OutboxSpy
    {
        private readonly IOutboxRepository _outbox;
        public OutboxSpy(IOutboxRepository outbox) => _outbox = outbox;

        public List<OutboxMessage> Sent =>
            _outbox.GetReadyBatchAsync(100, DateTime.UtcNow.AddDays(1)).GetAwaiter().GetResult().ToList();
    }

    private sealed class ManualClock : IClock
    {
        private DateTime _now;
        public ManualClock(DateTime initialUtcNow) => _now = initialUtcNow;
        public DateTime UtcNow => _now;
        public void Advance(TimeSpan by) => _now = _now.Add(by);
    }
}
