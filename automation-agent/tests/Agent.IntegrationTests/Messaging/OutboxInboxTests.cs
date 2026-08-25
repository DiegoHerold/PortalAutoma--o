using Biason.AutomationAgent.Application.Messaging;
using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Connections;
using Biason.AutomationAgent.Domain.Models.Messaging;
using Biason.AutomationAgent.IntegrationTests.Helpers;
using Biason.AutomationAgent.Protocol.Envelope;
using Biason.AutomationAgent.Protocol.Messages;
using Biason.AutomationAgent.Protocol.Serialization;
using FluentAssertions;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.Extensions.Options;
using Xunit;

namespace Biason.AutomationAgent.IntegrationTests.Messaging;

public sealed class OutboxInboxTests : IAsyncLifetime
{
    private readonly TestHelper _helper = new();

    public async Task InitializeAsync()
    {
        await _helper.InitializeDatabaseAsync();
        await _helper.SeedRegisteredAgentAsync(agentId: "agt_msg", credentialValue: "segredo-teste");
    }

    public Task DisposeAsync()
    {
        _helper.Dispose();
        return Task.CompletedTask;
    }

    // === outbox-persist-before-send + offline-spool ===

    [Fact]
    public async Task Outbox_PersistsBeforeSend_AndOfflineSpool_DoesNotLoseMessage()
    {
        var outbox = _helper.CreateOutboxRepository();
        var publisher = CreatePublisher(outbox);

        var persisted = await publisher.EnqueueAsync(
            PortalMessageTypes.ExecutionProgress,
            new { current = 1, total = 10 },
            executionId: "exec_1",
            executionAttemptId: "att_1",
            sequence: 1);

        persisted.Status.Should().Be(OutboxMessageStatus.Pending);
        (await outbox.GetByMessageIdAsync(persisted.MessageId)).Should().NotBeNull();

        var connection = new RecordingPortalConnectionManager { CurrentState = ConnectionState.Disconnected };
        var sender = CreateSender(outbox, connection);

        var sent = await sender.DispatchOnceAsync();

        sent.Should().Be(0);
        connection.SentSerialized.Should().BeEmpty();
        (await outbox.GetByMessageIdAsync(persisted.MessageId))!.Status.Should().Be(OutboxMessageStatus.Pending);
    }

    // === acknowledgement ===

    [Fact]
    public async Task Outbox_DispatchesPersistedEnvelope_AndMessageAckConfirmsIt()
    {
        var outbox = _helper.CreateOutboxRepository();
        var publisher = CreatePublisher(outbox);
        var connection = new RecordingPortalConnectionManager();
        var sender = CreateSender(outbox, connection);

        var persisted = await publisher.EnqueueAsync(
            PortalMessageTypes.ExecutionStarted,
            new { pid = 1234 },
            executionId: "exec_2",
            executionAttemptId: "att_2",
            sequence: 1);

        (await sender.DispatchOnceAsync()).Should().Be(1);
        connection.SentSerialized.Should().ContainSingle();

        var sentEnvelope = ProtocolJson.Deserialize<ProtocolEnvelope>(connection.SentSerialized[0]);
        sentEnvelope!.MessageId.Should().Be(persisted.MessageId);
        sentEnvelope.MessageType.Should().Be(PortalMessageTypes.ExecutionStarted);
        sentEnvelope.AgentId.Should().Be("agt_msg");

        (await outbox.GetByMessageIdAsync(persisted.MessageId))!.Status.Should().Be(OutboxMessageStatus.Sent);

        var ackService = new PortalMessageAcknowledgementService(
            connection,
            outbox,
            _helper.CreateAcknowledgementRepository(),
            _helper.Clock,
            NullLogger<PortalMessageAcknowledgementService>.Instance);

        await ackService.HandleMessageAsync(new InboundPortalMessage(
            MessageId: "msg_ack_1",
            MessageType: PortalMessageTypes.MessageAck,
            CorrelationId: persisted.MessageId,
            ExecutionId: null,
            ExecutionAttemptId: null,
            Sequence: null,
            Payload: new MessageAcknowledgementPayload { MessageId = persisted.MessageId },
            ReceivedAtUtc: _helper.Clock.UtcNow));

        var acknowledged = await outbox.GetByMessageIdAsync(persisted.MessageId);
        acknowledged!.Status.Should().Be(OutboxMessageStatus.Acknowledged);
        acknowledged.AcknowledgedAtUtc.Should().NotBeNull();
    }

    // === outbox-replay + restart-with-pending-events ===

    [Fact]
    public async Task Outbox_ReplaysUnacknowledgedMessage_WithSameMessageId()
    {
        var outbox = _helper.CreateOutboxRepository();
        var publisher = CreatePublisher(outbox);
        var connection = new RecordingPortalConnectionManager();
        var sender = CreateSender(outbox, connection);

        var persisted = await publisher.EnqueueAsync(
            PortalMessageTypes.ExecutionLog,
            new { level = "info", message = "linha 1" },
            executionId: "exec_3",
            executionAttemptId: "att_3",
            sequence: 1);

        (await sender.DispatchOnceAsync()).Should().Be(1);

        await outbox.MarkSentAsync(persisted.Id, _helper.Clock.UtcNow.AddMinutes(-10));
        await outbox.RecoverTimedOutAsync(
            _helper.Clock.UtcNow,
            TimeSpan.FromMinutes(1),
            maxAttempts: 5);

        (await sender.DispatchOnceAsync()).Should().Be(1);
        connection.SentSerialized.Should().HaveCount(2);

        var first = ProtocolJson.Deserialize<ProtocolEnvelope>(connection.SentSerialized[0]);
        var replay = ProtocolJson.Deserialize<ProtocolEnvelope>(connection.SentSerialized[1]);
        replay!.MessageId.Should().Be(first!.MessageId);
        replay.MessageId.Should().Be(persisted.MessageId);
    }

    [Fact]
    public async Task Outbox_AssignsContiguousAttemptSequences_WhenSequenceIsOmitted()
    {
        var outbox = _helper.CreateOutboxRepository();
        var publisher = CreatePublisher(outbox);

        var preparing = await publisher.EnqueueAsync(
            PortalMessageTypes.ExecutionPreparing,
            new { execution_id = "exec_seq", execution_attempt_id = "att_seq" },
            executionId: "exec_seq",
            executionAttemptId: "att_seq");

        var log = await publisher.EnqueueAsync(
            PortalMessageTypes.ExecutionLog,
            new { level = "info", message = "line" },
            executionId: "exec_seq",
            executionAttemptId: "att_seq");

        var metric = await publisher.EnqueueAsync(
            PortalMessageTypes.ExecutionMetric,
            new { metric_name = "items_processed", value = 1 },
            executionId: "exec_seq",
            executionAttemptId: "att_seq");

        preparing.Sequence.Should().Be(1);
        log.Sequence.Should().Be(2);
        metric.Sequence.Should().Be(3);
        preparing.PayloadJson.Should().Contain("\"event_sequence\":1");
        log.PayloadJson.Should().Contain("\"event_sequence\":2");
        metric.PayloadJson.Should().Contain("\"event_sequence\":3");
    }

    // === duplicated-event ===

    [Fact]
    public async Task Outbox_DeduplicatesByMessageId()
    {
        var outbox = _helper.CreateOutboxRepository();
        var publisher = CreatePublisher(outbox);

        var first = await publisher.EnqueueAsync(
            PortalMessageTypes.ExecutionMetric,
            new { name = "cpu", value = 10 },
            executionAttemptId: "att_dup",
            sequence: 1,
            messageId: "msg_fixed_outbox");

        var second = await publisher.EnqueueAsync(
            PortalMessageTypes.ExecutionMetric,
            new { name = "cpu", value = 99 },
            executionAttemptId: "att_dup",
            sequence: 1,
            messageId: "msg_fixed_outbox");

        second.Id.Should().Be(first.Id);
        (await outbox.GetDiagnosticsAsync()).Pending.Should().Be(1);
        (await outbox.GetByMessageIdAsync("msg_fixed_outbox"))!.PayloadJson.Should().Contain("\"value\":10");
    }

    // === dead-letter ===

    [Fact]
    public async Task Outbox_OversizedMessage_IsPersistedAsDeadLetter()
    {
        var outbox = _helper.CreateOutboxRepository();
        var publisher = CreatePublisher(outbox);

        var oversized = new string('x', ProtocolConstants.MaxMessageSizeBytes + 1024);
        var persisted = await publisher.EnqueueAsync(
            PortalMessageTypes.ExecutionLog,
            new { message = oversized },
            executionId: "exec_big",
            executionAttemptId: "att_big",
            sequence: 1);

        persisted.Status.Should().Be(OutboxMessageStatus.DeadLetter);
        persisted.LastError.Should().Contain("excede o limite");

        var connection = new RecordingPortalConnectionManager();
        var sender = CreateSender(outbox, connection);

        (await sender.DispatchOnceAsync()).Should().Be(0);
        connection.SentSerialized.Should().BeEmpty();
    }

    // === inbox-deduplication + persist-before-processing ===

    [Fact]
    public async Task Inbox_StoresBeforeProcessing_AndDeduplicatesCommand()
    {
        var inbox = _helper.CreateInboxRepository();
        var outbox = _helper.CreateOutboxRepository();
        var publisher = CreatePublisher(outbox);
        var connection = new RecordingPortalConnectionManager();
        var portalInbox = CreatePortalInbox(inbox, publisher, connection);

        var inbound = new InboundPortalMessage(
            MessageId: "msg_cmd_1",
            MessageType: PortalMessageTypes.SyncRequest,
            CorrelationId: null,
            ExecutionId: null,
            ExecutionAttemptId: null,
            Sequence: 1,
            Payload: new { reason = "test" },
            ReceivedAtUtc: _helper.Clock.UtcNow);

        await portalInbox.HandleMessageAsync(inbound);
        await portalInbox.HandleMessageAsync(inbound);

        (await inbox.GetDiagnosticsAsync()).Pending.Should().Be(1);

        var handler = new RecordingCommandHandler(
            PortalMessageTypes.SyncRequest,
            async command =>
            {
                (await inbox.GetByMessageIdAsync(command.MessageId)).Should().NotBeNull();
                return InboxCommandHandlerResult.Processed("ok");
            });

        var processor = CreateProcessor(inbox, portalInbox, handler);

        (await processor.ProcessOnceAsync()).Should().Be(1);
        handler.Calls.Should().Be(1);

        var processed = await inbox.GetByMessageIdAsync("msg_cmd_1");
        processed!.Status.Should().Be(InboxCommandStatus.Processed);

        var commandAck = (await outbox.GetReadyBatchAsync(10, _helper.Clock.UtcNow)).Single();
        commandAck.MessageType.Should().Be(PortalMessageTypes.CommandAck);
        commandAck.PayloadJson.Should().Contain("msg_cmd_1");
    }

    [Fact]
    public async Task Inbox_HandlerFailuresEventuallyDeadLetterCommand()
    {
        var inbox = _helper.CreateInboxRepository();
        var outbox = _helper.CreateOutboxRepository();
        var publisher = CreatePublisher(outbox);
        var connection = new RecordingPortalConnectionManager();
        var portalInbox = CreatePortalInbox(inbox, publisher, connection);

        await portalInbox.HandleMessageAsync(new InboundPortalMessage(
            MessageId: "msg_cmd_dead",
            MessageType: PortalMessageTypes.SyncRequest,
            CorrelationId: null,
            ExecutionId: null,
            ExecutionAttemptId: null,
            Sequence: 1,
            Payload: new { reason = "dead-letter-test" },
            ReceivedAtUtc: _helper.Clock.UtcNow));

        var handler = new RecordingCommandHandler(
            PortalMessageTypes.SyncRequest,
            _ => throw new InvalidOperationException("boom"));

        var processor = CreateProcessor(inbox, portalInbox, handler, maxAttempts: 2);

        (await processor.ProcessOnceAsync()).Should().Be(0);
        (await processor.ProcessOnceAsync()).Should().Be(1);

        var command = await inbox.GetByMessageIdAsync("msg_cmd_dead");
        command!.Status.Should().Be(InboxCommandStatus.DeadLetter);
        command.Error.Should().Be("boom");

        var ack = (await outbox.GetReadyBatchAsync(10, _helper.Clock.UtcNow)).Single();
        ack.MessageType.Should().Be(PortalMessageTypes.CommandAck);
        ack.PayloadJson.Should().Contain(InboxCommandStatus.DeadLetter);
    }

    // === Bloco 5.5, seção 41/48 — unknown-command-rejected ===
    // Antes da correção, um comando sem handler ficava `pending` para sempre
    // (InboxCommandProcessor apenas dava `continue`). Agora deve virar
    // dead-letter com UNSUPPORTED_COMMAND e gerar ACK, sem exigir handler.
    [Fact]
    public async Task Inbox_CommandWithoutRegisteredHandler_IsDeadLetteredAsUnsupported()
    {
        var inbox = _helper.CreateInboxRepository();
        var outbox = _helper.CreateOutboxRepository();
        var publisher = CreatePublisher(outbox);
        var connection = new RecordingPortalConnectionManager();
        var portalInbox = CreatePortalInbox(inbox, publisher, connection);

        await portalInbox.HandleMessageAsync(new InboundPortalMessage(
            MessageId: "msg_no_handler",
            MessageType: PortalMessageTypes.ExecutionOffer,
            CorrelationId: null,
            ExecutionId: "exec_nh",
            ExecutionAttemptId: null,
            Sequence: 1,
            Payload: new { automation_id = "automation_x" },
            ReceivedAtUtc: _helper.Clock.UtcNow));

        // Processor sem nenhum IInboxCommandHandler registrado para execution.offer.
        var processor = new InboxCommandProcessor(
            inbox,
            Array.Empty<IInboxCommandHandler>(),
            portalInbox,
            _helper.Clock,
            Options.Create(DefaultMessagingOptions()),
            NullLogger<InboxCommandProcessor>.Instance);

        (await processor.ProcessOnceAsync()).Should().Be(1);

        var command = await inbox.GetByMessageIdAsync("msg_no_handler");
        command!.Status.Should().Be(InboxCommandStatus.DeadLetter);
        command.Error.Should().Be("UNSUPPORTED_COMMAND");

        var ack = (await outbox.GetReadyBatchAsync(10, _helper.Clock.UtcNow)).Single();
        ack.MessageType.Should().Be(PortalMessageTypes.CommandAck);
        ack.PayloadJson.Should().Contain("UNSUPPORTED_COMMAND");
        ack.PayloadJson.Should().Contain(InboxCommandStatus.DeadLetter);
    }

    private OutboxMessagePublisher CreatePublisher(IOutboxRepository outbox)
    {
        return new OutboxMessagePublisher(outbox, _helper.CreateIdentityRepository(), _helper.Clock);
    }

    private OutboxBatchSender CreateSender(IOutboxRepository outbox, RecordingPortalConnectionManager connection)
    {
        return new OutboxBatchSender(
            outbox,
            connection,
            _helper.CreateIdentityRepository(),
            _helper.Clock,
            Options.Create(DefaultMessagingOptions()),
            NullLogger<OutboxBatchSender>.Instance);
    }

    private PortalInboxService CreatePortalInbox(
        IInboxRepository inbox,
        OutboxMessagePublisher publisher,
        RecordingPortalConnectionManager connection)
    {
        return new PortalInboxService(
            connection,
            inbox,
            publisher,
            _helper.CreateAcknowledgementRepository(),
            _helper.Clock,
            NullLogger<PortalInboxService>.Instance);
    }

    private InboxCommandProcessor CreateProcessor(
        IInboxRepository inbox,
        PortalInboxService portalInbox,
        IInboxCommandHandler handler,
        int maxAttempts = 5)
    {
        return new InboxCommandProcessor(
            inbox,
            new[] { handler },
            portalInbox,
            _helper.Clock,
            Options.Create(MessagingOptionsWithMaxAttempts(maxAttempts)),
            NullLogger<InboxCommandProcessor>.Instance);
    }

    private static MessagingOptions DefaultMessagingOptions() => new()
    {
        OutboxBatchSize = 500,
        PollIntervalSeconds = 1,
        AcknowledgementTimeoutSeconds = 30,
        MaxAttempts = 5,
        RetryDelaySeconds = 1
    };

    private static MessagingOptions MessagingOptionsWithMaxAttempts(int maxAttempts) => new()
    {
        OutboxBatchSize = 500,
        PollIntervalSeconds = 1,
        AcknowledgementTimeoutSeconds = 30,
        MaxAttempts = maxAttempts,
        RetryDelaySeconds = 1
    };

    private sealed class RecordingPortalConnectionManager : IPortalConnectionManager
    {
        public ConnectionState CurrentState { get; init; } = ConnectionState.Connected;
        public List<string> SentSerialized { get; } = new();

        public event Func<ConnectionState, ConnectionState, Task>? StateChanged { add { } remove { } }
        public event Func<InboundPortalMessage, Task>? MessageReceived { add { } remove { } }

        public Task RunAsync(CancellationToken ct) => Task.CompletedTask;

        public Task<bool> TrySendAsync(string messageType, object payload, string? correlationId = null, CancellationToken ct = default) =>
            throw new NotSupportedException("Tests use serialized durable sends.");

        public Task<bool> TrySendSerializedAsync(string serializedEnvelope, CancellationToken ct = default)
        {
            if (CurrentState is not (ConnectionState.Connected or ConnectionState.Degraded))
                return Task.FromResult(false);

            SentSerialized.Add(serializedEnvelope);
            return Task.FromResult(true);
        }

        public Task DisableAsync(string reason, CancellationToken ct = default) => Task.CompletedTask;
        public Task EnableAsync(CancellationToken ct = default) => Task.CompletedTask;

        public ConnectionStatus GetStatus() => new()
        {
            ConnectionId = "test-connection",
            State = CurrentState,
            Endpoint = "wss://test"
        };

        public ValueTask DisposeAsync() => ValueTask.CompletedTask;
    }

    private sealed class RecordingCommandHandler : IInboxCommandHandler
    {
        private readonly Func<InboxCommand, Task<InboxCommandHandlerResult>> _handler;

        public RecordingCommandHandler(string messageType, Func<InboxCommand, Task<InboxCommandHandlerResult>> handler)
        {
            MessageType = messageType;
            _handler = handler;
        }

        public string MessageType { get; }
        public int Calls { get; private set; }

        public async Task<InboxCommandHandlerResult> HandleAsync(InboxCommand command, CancellationToken ct = default)
        {
            Calls++;
            return await _handler(command);
        }
    }
}
