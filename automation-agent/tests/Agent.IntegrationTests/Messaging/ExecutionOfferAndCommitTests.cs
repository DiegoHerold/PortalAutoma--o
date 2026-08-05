using System.Text.Json;
using Biason.AutomationAgent.Application.Capacity;
using Biason.AutomationAgent.Application.Messaging;
using Biason.AutomationAgent.Application.Messaging.Handlers;
using Biason.AutomationAgent.Application.Validation;
using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Connections;
using Biason.AutomationAgent.Domain.Models.Execution;
using Biason.AutomationAgent.Domain.Models.Messaging;
using Biason.AutomationAgent.Domain.Models.Storage;
using Biason.AutomationAgent.Infrastructure.Persistence;
using Biason.AutomationAgent.Infrastructure.Stores;
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
/// Bloco 5.5, seção 49 — fluxo remoto ponta a ponta mínimo:
/// execution.offer -&gt; accept -&gt; execution.commit -&gt; PREPARING -&gt; ExecutionManager.
/// Usa repositórios SQLite reais e um fake de ExecutionManager (o teste real
/// de lançamento de processo é responsabilidade dos testes de
/// Execution/ExecutionManager já existentes — aqui o que se valida é a
/// coordenação: Admission -&gt; reserva -&gt; commit atômico -&gt; disparo).
/// </summary>
public sealed class ExecutionOfferAndCommitTests : IAsyncLifetime
{
    private readonly TestHelper _helper = new();
    private string _packageId = default!;

    public async Task InitializeAsync()
    {
        await _helper.InitializeDatabaseAsync();
        await _helper.SeedRegisteredAgentAsync(agentId: "agt_offer", credentialValue: "segredo-teste");
        _packageId = await SeedValidPackageAsync();
    }

    public Task DisposeAsync()
    {
        _helper.Dispose();
        return Task.CompletedTask;
    }

    // === offer-valid + commit-valid + commit-starts-preparing ===

    [Fact]
    public async Task OfferThenCommit_HappyPath_AcceptsOfferAndDispatchesExecution()
    {
        var fx = CreateFixture();
        var attemptId = "att_offer_1";
        var executionId = "exec_offer_1";

        var offerCommand = BuildOfferCommand(executionId, attemptId, "off_1");
        var offerResult = await fx.OfferHandler.HandleAsync(offerCommand);

        offerResult.Success.Should().BeTrue();
        var accepted = fx.Outbox.Sent.Should().ContainSingle(m => m.MessageType == PortalMessageTypes.ExecutionAccept).Which;
        var acceptPayload = ProtocolJson.Deserialize<ExecutionAcceptPayload>(accepted.PayloadJson);
        acceptPayload!.ResourceReservations.Should().NotBeNullOrEmpty();
        acceptPayload.AgentId.Should().Be("agt_offer");

        var execution = await fx.ExecutionRepo.GetAsync(executionId);
        execution!.CurrentState.Should().Be(ExecutionState.Reserved);

        var commitCommand = BuildCommitCommand(executionId, attemptId, "off_1", "lease_1");
        var commitResult = await fx.CommitHandler.HandleAsync(commitCommand);

        commitResult.Success.Should().BeTrue();
        commitResult.Result.Should().Be("committed");

        var committedExecution = await fx.ExecutionRepo.GetAsync(executionId);
        committedExecution!.CurrentState.Should().Be(ExecutionState.Committed);

        var lease = await fx.LeaseRepo.GetAsync("lease_1");
        lease.Should().NotBeNull();
        lease!.State.Should().Be(LeaseState.Active);

        fx.Outbox.Sent.Should().Contain(m => m.MessageType == PortalMessageTypes.ExecutionEventBatch);
        fx.Outbox.Sent.Should().NotContain(m => m.MessageType == PortalMessageTypes.ExecutionStarted,
            "execution.started is emitted only after ExecutionManager launches the real host/process");

        // ExecuteAsync é disparado fire-and-forget — aguarda o Task.Run interno.
        await WaitUntilAsync(() => fx.ExecutionManager.ReceivedCalls().Any());
        await fx.ExecutionManager.Received(1).ExecuteAsync(
            Arg.Is<Domain.Models.ExecutionRecord>(e => e.ExecutionId == executionId),
            Arg.Any<Domain.Models.AutomationManifest>(),
            Arg.Any<string?>(),
            Arg.Any<CancellationToken>());
    }

    // === offer-reject ===

    [Fact]
    public async Task Offer_RejectedByAdmission_SendsExecutionReject_AndDoesNotCreateReservation()
    {
        var fx = CreateFixture(backgroundSlots: 0); // capacidade zero força rejeição
        var command = BuildOfferCommand("exec_reject_1", "att_reject_1", "off_reject_1");

        var result = await fx.OfferHandler.HandleAsync(command);

        result.Success.Should().BeTrue();
        fx.Outbox.Sent.Should().ContainSingle(m => m.MessageType == PortalMessageTypes.ExecutionReject);

        var execution = await fx.ExecutionRepo.GetAsync("exec_reject_1");
        execution!.CurrentState.Should().Be(ExecutionState.Rejected);
    }

    // === offer-duplicate ===

    [Fact]
    public async Task Offer_DuplicateIdenticalPayload_ResendsSameDecision_WithoutCreatingSecondReservation()
    {
        var fx = CreateFixture();
        var command = BuildOfferCommand("exec_dup_1", "att_dup_1", "off_dup_1");

        await fx.OfferHandler.HandleAsync(command);

        // Mesmo payload, "reentrega" simulada (mesmo message_id — na prática o
        // Inbox já dedupa nesse caso; aqui validamos a idempotência no nível
        // do handler, defesa em profundidade).
        var result = await fx.OfferHandler.HandleAsync(command);

        result.Success.Should().BeTrue();
        result.Result.Should().Be("duplicate_offer_resent");
        // Duas respostas accept são esperadas (uma por chamada — entrega
        // "at-least-once" é aceitável); o que não pode duplicar é a reserva.
        fx.Outbox.Sent.Count(m => m.MessageType == PortalMessageTypes.ExecutionAccept).Should().Be(2);

        var active = await fx.ReservationRepo.GetActiveAsync();
        active.Should().ContainSingle();
    }

    // === offer-conflict ===

    [Fact]
    public async Task Offer_SameAttemptDifferentPayload_IsRejectedAsConflict()
    {
        var fx = CreateFixture();
        var first = BuildOfferCommand("exec_conflict_1", "att_conflict_1", "off_conflict_1");
        await fx.OfferHandler.HandleAsync(first);

        var second = BuildOfferCommand("exec_conflict_1", "att_conflict_1", "off_conflict_2", messageId: "msg_offer_conflict_2");
        var result = await fx.OfferHandler.HandleAsync(second);

        result.Success.Should().BeTrue();
        result.Result.Should().Be("offer_conflict_rejected");
        var rejectMsg = fx.Outbox.Sent.Should().ContainSingle(m => m.MessageType == PortalMessageTypes.ExecutionReject).Which;
        var rejectPayload = ProtocolJson.Deserialize<ExecutionRejectPayload>(rejectMsg.PayloadJson);
        rejectPayload!.RejectionCode.Should().Be("PROTOCOL_INCOMPATIBLE");
    }

    // === commit-duplicate ===

    [Fact]
    public async Task Commit_ArrivingTwiceWithDifferentMessageIds_IsIdempotent()
    {
        var fx = CreateFixture();
        var attemptId = "att_commit_dup";
        var executionId = "exec_commit_dup";
        await fx.OfferHandler.HandleAsync(BuildOfferCommand(executionId, attemptId, "off_commit_dup"));

        var first = BuildCommitCommand(executionId, attemptId, "off_commit_dup", "lease_dup", messageId: "msg_commit_dup_1");
        var firstResult = await fx.CommitHandler.HandleAsync(first);
        firstResult.Result.Should().Be("committed");
        await WaitUntilAsync(() => fx.ExecutionManager.ReceivedCalls().Any());

        var second = BuildCommitCommand(executionId, attemptId, "off_commit_dup", "lease_dup", messageId: "msg_commit_dup_2");
        var secondResult = await fx.CommitHandler.HandleAsync(second);

        secondResult.Success.Should().BeTrue();
        secondResult.Result.Should().Be("duplicate_commit");
        await fx.ExecutionManager.Received(1).ExecuteAsync(Arg.Any<Domain.Models.ExecutionRecord>(), Arg.Any<Domain.Models.AutomationManifest>(), Arg.Any<string?>(), Arg.Any<CancellationToken>());
    }

    // === commit-invalid-reservation ===

    [Fact]
    public async Task Commit_WithoutPriorOffer_IsDeadLettered()
    {
        var fx = CreateFixture();
        var command = BuildCommitCommand("exec_no_offer", "att_no_offer", "off_none", "lease_none");

        var result = await fx.CommitHandler.HandleAsync(command);

        result.Success.Should().BeFalse();
        result.DeadLetter.Should().BeTrue();
        result.Error.Should().Be("EXECUTION_NOT_FOUND");
    }

    // === commit-expired / commit-expiration-race ===

    [Fact]
    public async Task Commit_AfterReservationExpired_IsRejectedWithReservationExpired()
    {
        var fx = CreateFixture(reservationTimeoutSeconds: 60);
        var attemptId = "att_commit_exp";
        var executionId = "exec_commit_exp";
        await fx.OfferHandler.HandleAsync(BuildOfferCommand(executionId, attemptId, "off_commit_exp"));

        fx.Clock.Advance(TimeSpan.FromSeconds(61));

        var command = BuildCommitCommand(executionId, attemptId, "off_commit_exp", "lease_exp");
        var result = await fx.CommitHandler.HandleAsync(command);

        result.Success.Should().BeTrue();
        result.Result.Should().Be("commit_rejected");
        fx.Outbox.Sent.Should().Contain(m => m.MessageType == PortalMessageTypes.ExecutionFailed);

        var execution = await fx.ExecutionRepo.GetAsync(executionId);
        execution!.CurrentState.Should().Be(ExecutionState.Cancelled);

        await fx.ExecutionManager.DidNotReceive().ExecuteAsync(Arg.Any<Domain.Models.ExecutionRecord>(), Arg.Any<Domain.Models.AutomationManifest>(), Arg.Any<string?>(), Arg.Any<CancellationToken>());
    }

    private static async Task WaitUntilAsync(Func<bool> condition, int timeoutMs = 2000)
    {
        var deadline = DateTime.UtcNow.AddMilliseconds(timeoutMs);
        while (!condition() && DateTime.UtcNow < deadline)
            await Task.Delay(10);
    }

    private InboxCommand BuildOfferCommand(string executionId, string attemptId, string offerId, string? messageId = null)
    {
        var payload = new ExecutionOfferPayload
        {
            ExecutionOfferId = offerId,
            ExecutionAttemptId = attemptId,
            TaskExecutionId = executionId,
            AutomationVersionId = _packageId,
            Runtime = new ExecutionOfferRuntime { Id = "python-core", Version = "3.13" },
            Package = new ExecutionOfferPackage { Id = _packageId, Sha256 = "n-a" },
            Input = JsonDocument.Parse("{}").RootElement.Clone(),
            RequiredPools = new[] { "background" },
            ExpiresAt = DateTime.UtcNow.AddMinutes(1)
        };

        return new InboxCommand
        {
            Id = Random.Shared.Next(1, int.MaxValue),
            MessageId = messageId ?? $"msg_{offerId}",
            CommandType = PortalMessageTypes.ExecutionOffer,
            PayloadJson = ProtocolJson.Serialize(payload),
            ExecutionId = executionId,
            ExecutionAttemptId = attemptId,
            ReceivedAtUtc = DateTime.UtcNow,
            Status = InboxCommandStatus.Processing
        };
    }

    private InboxCommand BuildCommitCommand(string executionId, string attemptId, string offerId, string leaseId, string? messageId = null)
    {
        var payload = new ExecutionCommitPayload
        {
            ExecutionOfferId = offerId,
            ExecutionAttemptId = attemptId,
            LeaseId = leaseId,
            LeaseExpiresAt = DateTime.UtcNow.AddMinutes(5)
        };

        return new InboxCommand
        {
            Id = Random.Shared.Next(1, int.MaxValue),
            MessageId = messageId ?? $"msg_{leaseId}",
            CommandType = PortalMessageTypes.ExecutionCommit,
            PayloadJson = ProtocolJson.Serialize(payload),
            ExecutionId = executionId,
            ExecutionAttemptId = attemptId,
            ReceivedAtUtc = DateTime.UtcNow,
            Status = InboxCommandStatus.Processing
        };
    }

    private async Task<string> SeedValidPackageAsync()
    {
        const string packageId = "pkg_test_1";
        var packageDir = Path.Combine(_helper.Dirs.PackagesPath, packageId);
        Directory.CreateDirectory(packageDir);

        var manifestPath = Path.Combine(packageDir, "automation.json");
        await File.WriteAllTextAsync(manifestPath, """
            {
              "schema_version": 1,
              "id": "test.automation",
              "name": "Test Automation",
              "version": "1.0.0",
              "runtime": { "id": "python-core", "version": "3.13" },
              "entrypoint": { "type": "python_function", "module": "automation.main", "callable": "run" },
              "resources": { "pool": "background", "slots": 1 },
              "timeout": { "execution_seconds": 3600, "graceful_shutdown_seconds": 30 }
            }
            """);

        var artifactRepo = new PackageArtifactRepository(_helper.DbManager);
        await artifactRepo.SaveAsync(new PackageArtifact
        {
            PackageId = packageId,
            AutomationId = "test.automation",
            AutomationVersionId = packageId,
            Version = "1.0.0",
            Sha256 = "n-a",
            SizeBytes = new FileInfo(manifestPath).Length,
            StorePath = packageDir,
            ManifestPath = manifestPath,
            DownloadedAtUtc = DateTime.UtcNow,
            VerifiedAtUtc = DateTime.UtcNow,
            IsValid = true
        });

        return packageId;
    }

    private TestFixture CreateFixture(int backgroundSlots = 5, int reservationTimeoutSeconds = 300)
    {
        var executionRepo = new ExecutionRepository(_helper.DbManager);
        var reservationRepo = new ReservationRepository(_helper.DbManager);
        var offerRepo = new ExecutionOfferRepository(_helper.DbManager);
        var commitRepo = new ExecutionCommitRepository(_helper.DbManager);
        var leaseRepo = new ExecutionLeaseRepository(_helper.DbManager);
        var packageArtifactRepo = new PackageArtifactRepository(_helper.DbManager);
        var capabilityRepo = _helper.CreateCapabilityRepository();

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

        var execOptions = Options.Create(new ExecutionOptions { ReservationTimeoutSeconds = reservationTimeoutSeconds });
        var reservations = new ResourceReservationManager(reservationRepo, capacity, clock, execOptions, NullLogger<ResourceReservationManager>.Instance);

        var stateManager = Substitute.For<IAgentStateManager>();
        stateManager.CurrentState.Returns(AgentState.Ready);

        var admission = new Application.Capacity.AdmissionController(
            capacity, reservations, capabilityRepo, stateManager, NullLogger<Application.Capacity.AdmissionController>.Instance);

        var manifestValidator = new ManifestValidator(NullLogger<ManifestValidator>.Instance);

        var packageStore = new PackageStore(
            _helper.Dirs, Substitute.For<IIntegrityVerifier>(), packageArtifactRepo, clock, NullLogger<PackageStore>.Instance);

        var outboxRepo = _helper.CreateOutboxRepository();
        var agentIdentity = _helper.CreateIdentityRepository();
        var outboxPublisher = new OutboxMessagePublisher(outboxRepo, agentIdentity, clock);
        var outboxSpy = new OutboxSpy(outboxRepo);

        var executionManager = Substitute.For<IExecutionManager>();
        executionManager
            .ExecuteAsync(Arg.Any<Domain.Models.ExecutionRecord>(), Arg.Any<Domain.Models.AutomationManifest>(), Arg.Any<string?>(), Arg.Any<CancellationToken>())
            .Returns(Task.FromResult(new Domain.Models.Execution.ExecutionResult
            {
                ExecutionId = "n-a",
                AttemptId = "n-a",
                Success = true,
                ExitCode = 0,
                CompletedAtUtc = DateTime.UtcNow
            }));

        var downloadManager = Substitute.For<IDownloadManager>();

        var offerHandler = new ExecutionOfferHandler(
            offerRepo, executionRepo, packageStore, manifestValidator, admission, reservations,
            agentIdentity, outboxPublisher, downloadManager, _helper.Dirs, clock, NullLogger<ExecutionOfferHandler>.Instance);

        var commitHandler = new ExecutionCommitHandler(
            commitRepo, executionRepo, offerRepo, leaseRepo, reservations, packageStore, manifestValidator,
            executionManager, outboxPublisher, clock, NullLogger<ExecutionCommitHandler>.Instance, desktopLocks: null);

        return new TestFixture(offerHandler, commitHandler, executionRepo, reservationRepo, leaseRepo, outboxSpy, executionManager, clock);
    }

    private sealed record TestFixture(
        ExecutionOfferHandler OfferHandler,
        ExecutionCommitHandler CommitHandler,
        ExecutionRepository ExecutionRepo,
        ReservationRepository ReservationRepo,
        ExecutionLeaseRepository LeaseRepo,
        OutboxSpy Outbox,
        IExecutionManager ExecutionManager,
        ManualClock Clock);

    /// <summary>
    /// Lê o Outbox real (SQLite) diretamente — evita duplicar um fake de
    /// transporte só para inspecionar o que foi enfileirado pelos handlers.
    /// Cada acesso reconsulta o banco (a fila pode crescer entre chamadas).
    /// </summary>
    private sealed class OutboxSpy
    {
        private readonly IOutboxRepository _outbox;
        public OutboxSpy(IOutboxRepository outbox) => _outbox = outbox;

        public List<Domain.Models.Messaging.OutboxMessage> Sent =>
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
