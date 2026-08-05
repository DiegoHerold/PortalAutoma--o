using System.Net;
using System.Text.Json;
using Biason.AutomationAgent.Application.Artifacts;
using Biason.AutomationAgent.Application.Messaging;
using Biason.AutomationAgent.Application.Messaging.Handlers;
using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Execution;
using Biason.AutomationAgent.Domain.Models.Messaging;
using Biason.AutomationAgent.Infrastructure.Http;
using Biason.AutomationAgent.Infrastructure.Persistence;
using Biason.AutomationAgent.IntegrationTests.Helpers;
using Biason.AutomationAgent.Protocol.Messages;
using Biason.AutomationAgent.Protocol.Serialization;
using FluentAssertions;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.Extensions.Options;
using Xunit;

namespace Biason.AutomationAgent.IntegrationTests.Artifacts;

public sealed class ArtifactPipelineTests : IAsyncLifetime
{
    private const string PayloadSha = "239f59ed55e737c77147cf55ad0c1b030b6d7ee748a7426952f9b852d5a935e5";
    private readonly TestHelper _helper = new();

    public async Task InitializeAsync()
    {
        await _helper.InitializeDatabaseAsync();
        await _helper.SeedRegisteredAgentAsync(agentId: "agt_artifacts", credentialValue: "segredo-teste");
    }

    public Task DisposeAsync()
    {
        _helper.Dispose();
        return Task.CompletedTask;
    }

    [Fact]
    public async Task ArtifactManager_RegisterAsync_PersistsAnnouncedArtifact_AndEnqueuesCreatedEvent()
    {
        var artifactRepo = new PendingArtifactRepository(_helper.DbManager);
        var outboxRepo = _helper.CreateOutboxRepository();
        var manager = new ArtifactManager(
            artifactRepo,
            CreatePublisher(outboxRepo),
            _helper.Clock,
            NullLogger<ArtifactManager>.Instance);

        var artifactPath = ArtifactPath("report.txt");
        await File.WriteAllTextAsync(artifactPath, "hello");

        await manager.RegisterAsync("exec_art_1", "att_art_1", new[]
        {
            new ExecutionArtifactRef
            {
                ArtifactId = "art_1",
                Name = "report.txt",
                ContentType = "text/plain",
                SizeBytes = 5,
                Sha256 = "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824",
                LocalPath = artifactPath
            }
        });

        var pending = await artifactRepo.GetAsync("art_1");
        pending!.Status.Should().Be(ArtifactStatus.Announced);
        pending.AnnouncementMessageId.Should().NotBeNullOrWhiteSpace();
        pending.UploadUrl.Should().BeNull();

        var outbox = await outboxRepo.GetReadyBatchAsync(10, _helper.Clock.UtcNow.AddMinutes(1));
        outbox.Should().ContainSingle(m =>
            m.MessageType == PortalMessageTypes.ExecutionArtifactCreated &&
            m.MessageId == pending.AnnouncementMessageId);
    }

    [Fact]
    public async Task AckDrivenLifecycle_StoresUploadInstructions_UploadsBytes_ThenConfirmsFromUploadedAck()
    {
        var artifactRepo = new PendingArtifactRepository(_helper.DbManager);
        var outboxRepo = _helper.CreateOutboxRepository();
        var manager = new ArtifactManager(
            artifactRepo,
            CreatePublisher(outboxRepo),
            _helper.Clock,
            NullLogger<ArtifactManager>.Instance);
        var ackHandler = new ArtifactAcknowledgementHandler(
            artifactRepo,
            NullLogger<ArtifactAcknowledgementHandler>.Instance);

        var artifactPath = ArtifactPath("upload.txt");
        await File.WriteAllTextAsync(artifactPath, "payload");

        await manager.RegisterAsync("exec_art", "att_art", new[]
        {
            new ExecutionArtifactRef
            {
                ArtifactId = "art_ack_lifecycle",
                Name = "upload.txt",
                ContentType = "text/plain",
                SizeBytes = 7,
                Sha256 = PayloadSha,
                LocalPath = artifactPath
            }
        });

        var created = (await outboxRepo.GetReadyBatchAsync(10, _helper.Clock.UtcNow.AddMinutes(1)))
            .Single(m => m.MessageType == PortalMessageTypes.ExecutionArtifactCreated);
        var createdAck = new MessageAcknowledgementPayload
        {
            Ok = true,
            MessageId = created.MessageId,
            MessageType = PortalMessageTypes.ExecutionArtifactCreated,
            Result = ResultElement(new
            {
                artifact = new { id = "art_ack_lifecycle", status = "created" },
                upload_url = "https://upload.example/art_ack_lifecycle",
                upload_session_id = "upl_ack_lifecycle",
                expires_at = _helper.Clock.UtcNow.AddMinutes(15)
            })
        };

        await ackHandler.HandleAsync(created, createdAck, _helper.Clock.UtcNow);
        await ackHandler.HandleAsync(created, createdAck, _helper.Clock.UtcNow);

        var instructed = await artifactRepo.GetAsync("art_ack_lifecycle");
        instructed!.Status.Should().Be(ArtifactStatus.UploadUrlReceived);
        instructed.UploadSessionId.Should().Be("upl_ack_lifecycle");

        var uploader = new RecordingArtifactContentUploader(PortalArtifactUploadOutcome.Ok());
        var uploadManager = CreateUploadManager(artifactRepo, outboxRepo, uploader);

        (await uploadManager.ProcessDueAsync()).Should().Be(1);

        var uploaded = await artifactRepo.GetAsync("art_ack_lifecycle");
        uploaded!.Status.Should().Be(ArtifactStatus.Uploaded);
        uploaded.UploadedMessageId.Should().NotBeNullOrWhiteSpace();
        File.Exists(artifactPath).Should().BeTrue("local cleanup waits for Portal confirmation");
        uploader.Uploads.Should().ContainSingle(u => u.Target.RemoteObjectId == "upl_ack_lifecycle");

        var uploadedMessage = (await outboxRepo.GetReadyBatchAsync(10, _helper.Clock.UtcNow.AddMinutes(1)))
            .Single(m => m.MessageType == PortalMessageTypes.ArtifactUploaded);
        uploadedMessage.MessageId.Should().Be(uploaded.UploadedMessageId);

        var uploadedAck = new MessageAcknowledgementPayload
        {
            Ok = true,
            MessageId = uploadedMessage.MessageId,
            MessageType = PortalMessageTypes.ArtifactUploaded,
            Result = ResultElement(new
            {
                id = "art_ack_lifecycle",
                status = "available",
                stored_object_id = "obj_ack_lifecycle",
                upload_session_id = "upl_ack_lifecycle"
            })
        };

        await ackHandler.HandleAsync(uploadedMessage, uploadedAck, _helper.Clock.UtcNow);
        await ackHandler.HandleAsync(uploadedMessage, uploadedAck, _helper.Clock.UtcNow);

        var confirmed = await artifactRepo.GetAsync("art_ack_lifecycle");
        confirmed!.Status.Should().Be(ArtifactStatus.Confirmed);
        confirmed.RemoteObjectId.Should().Be("obj_ack_lifecycle");
        File.Exists(artifactPath).Should().BeFalse();
    }

    [Fact]
    public async Task ArtifactUploadManager_ProcessDue_RetriesTransientUploadFailure()
    {
        var artifactRepo = new PendingArtifactRepository(_helper.DbManager);
        var outboxRepo = _helper.CreateOutboxRepository();
        var artifactPath = ArtifactPath("retry.txt");
        await File.WriteAllTextAsync(artifactPath, "payload");
        await artifactRepo.SaveAsync(CreatePendingArtifact("art_retry_1", artifactPath));

        var uploader = new RecordingArtifactContentUploader(
            PortalArtifactUploadOutcome.Failed("ARTIFACT_UPLOAD_HTTP_ERROR", "temporary", retryable: true));
        var manager = CreateUploadManager(artifactRepo, outboxRepo, uploader);

        (await manager.ProcessDueAsync()).Should().Be(1);

        var retry = await artifactRepo.GetAsync("art_retry_1");
        retry!.Status.Should().Be(ArtifactStatus.RetryWait);
        retry.AttemptCount.Should().Be(1);
        retry.LastError.Should().Be("ARTIFACT_UPLOAD_HTTP_ERROR");

        var outbox = await outboxRepo.GetReadyBatchAsync(10, _helper.Clock.UtcNow.AddMinutes(1));
        outbox.Should().NotContain(m => m.MessageType == PortalMessageTypes.ArtifactFailed);
    }

    [Fact]
    public async Task ArtifactUploadManager_ProcessDue_ReannouncesArtifactWhenUploadUrlExpired()
    {
        var artifactRepo = new PendingArtifactRepository(_helper.DbManager);
        var outboxRepo = _helper.CreateOutboxRepository();
        var artifactPath = ArtifactPath("expired.txt");
        await File.WriteAllTextAsync(artifactPath, "payload");
        await artifactRepo.SaveAsync(CreatePendingArtifact(
            "art_expired_url",
            artifactPath,
            uploadExpiresAtUtc: _helper.Clock.UtcNow.AddMinutes(-1)));

        var uploader = new RecordingArtifactContentUploader(PortalArtifactUploadOutcome.Ok());
        var manager = CreateUploadManager(artifactRepo, outboxRepo, uploader);

        (await manager.ProcessDueAsync()).Should().Be(1);

        var expired = await artifactRepo.GetAsync("art_expired_url");
        expired!.Status.Should().Be(ArtifactStatus.Announced);
        expired.AnnouncementMessageId.Should().NotBeNullOrWhiteSpace();
        uploader.Uploads.Should().BeEmpty();

        var outbox = await outboxRepo.GetReadyBatchAsync(10, _helper.Clock.UtcNow.AddMinutes(1));
        outbox.Should().ContainSingle(m => m.MessageType == PortalMessageTypes.ExecutionArtifactCreated);
    }

    [Fact]
    public async Task ArtifactUploadManager_ProcessDue_MarksMissingLocalFileAsFailed_AndPublishesFailure()
    {
        var artifactRepo = new PendingArtifactRepository(_helper.DbManager);
        var outboxRepo = _helper.CreateOutboxRepository();
        var missingPath = ArtifactPath("missing.txt");
        await artifactRepo.SaveAsync(CreatePendingArtifact("art_missing_1", missingPath));

        var uploader = new RecordingArtifactContentUploader(PortalArtifactUploadOutcome.Ok());
        var manager = CreateUploadManager(artifactRepo, outboxRepo, uploader);

        (await manager.ProcessDueAsync()).Should().Be(1);

        var missing = await artifactRepo.GetAsync("art_missing_1");
        missing!.Status.Should().Be(ArtifactStatus.Failed);
        missing.LastError.Should().Be("ARTIFACT_LOCAL_FILE_MISSING");
        uploader.Uploads.Should().BeEmpty();

        var outbox = await outboxRepo.GetReadyBatchAsync(10, _helper.Clock.UtcNow.AddMinutes(1));
        outbox.Should().ContainSingle(m => m.MessageType == PortalMessageTypes.ArtifactFailed);
    }

    [Fact]
    public async Task ArtifactUploadManager_ProcessDue_MarksHashMismatchAsFailed_BeforeUploading()
    {
        var artifactRepo = new PendingArtifactRepository(_helper.DbManager);
        var outboxRepo = _helper.CreateOutboxRepository();
        var artifactPath = ArtifactPath("mismatch.txt");
        await File.WriteAllTextAsync(artifactPath, "changed");
        await artifactRepo.SaveAsync(CreatePendingArtifact("art_hash_mismatch", artifactPath, sha256: PayloadSha));

        var uploader = new RecordingArtifactContentUploader(PortalArtifactUploadOutcome.Ok());
        var manager = CreateUploadManager(artifactRepo, outboxRepo, uploader);

        (await manager.ProcessDueAsync()).Should().Be(1);

        var failed = await artifactRepo.GetAsync("art_hash_mismatch");
        failed!.Status.Should().Be(ArtifactStatus.Failed);
        failed.LastError.Should().Be("ARTIFACT_LOCAL_FILE_HASH_MISMATCH");
        uploader.Uploads.Should().BeEmpty();
    }

    [Fact]
    public async Task ArtifactUploadManager_ProcessDue_BlocksPathOutsideArtifactsDirectory()
    {
        var artifactRepo = new PendingArtifactRepository(_helper.DbManager);
        var outboxRepo = _helper.CreateOutboxRepository();
        var artifactPath = Path.Combine(_helper.TempDir, "outside.txt");
        await File.WriteAllTextAsync(artifactPath, "payload");
        await artifactRepo.SaveAsync(CreatePendingArtifact("art_unsafe_path", artifactPath));

        var uploader = new RecordingArtifactContentUploader(PortalArtifactUploadOutcome.Ok());
        var manager = CreateUploadManager(artifactRepo, outboxRepo, uploader);

        (await manager.ProcessDueAsync()).Should().Be(1);

        var failed = await artifactRepo.GetAsync("art_unsafe_path");
        failed!.Status.Should().Be(ArtifactStatus.Failed);
        failed.LastError.Should().Be("ARTIFACT_LOCAL_PATH_UNAUTHORIZED");
        uploader.Uploads.Should().BeEmpty();
    }

    [Fact]
    public async Task ArtifactUploadManager_ProcessDue_UploadsMultipleArtifacts()
    {
        var artifactRepo = new PendingArtifactRepository(_helper.DbManager);
        var outboxRepo = _helper.CreateOutboxRepository();
        var firstPath = ArtifactPath("one.txt");
        var secondPath = ArtifactPath("two.txt");
        await File.WriteAllTextAsync(firstPath, "one");
        await File.WriteAllTextAsync(secondPath, "two");
        await artifactRepo.SaveAsync(CreatePendingArtifact(
            "art_one",
            firstPath,
            sizeBytes: 3,
            sha256: "7692c3ad3540bb803c020b3aee66cd8887123234ea0c6e7143c0add73ff431ed",
            uploadSessionId: "upl_one"));
        await artifactRepo.SaveAsync(CreatePendingArtifact(
            "art_two",
            secondPath,
            sizeBytes: 3,
            sha256: "3fc4ccfe745870e2c0d99f71f30ff0656c8dedd41cc1d7d3d376b0dbe685e2f3",
            uploadSessionId: "upl_two"));

        var uploader = new RecordingArtifactContentUploader(PortalArtifactUploadOutcome.Ok(), PortalArtifactUploadOutcome.Ok());
        var manager = CreateUploadManager(artifactRepo, outboxRepo, uploader);

        (await manager.ProcessDueAsync()).Should().Be(2);

        uploader.Uploads.Should().HaveCount(2);
        (await artifactRepo.GetAsync("art_one"))!.Status.Should().Be(ArtifactStatus.Uploaded);
        (await artifactRepo.GetAsync("art_two"))!.Status.Should().Be(ArtifactStatus.Uploaded);

        var outbox = await outboxRepo.GetReadyBatchAsync(10, _helper.Clock.UtcNow.AddMinutes(1));
        outbox.Where(m => m.MessageType == PortalMessageTypes.ArtifactUploaded).Should().HaveCount(2);
    }

    [Fact]
    public async Task ArtifactUploadManager_RecoverUploading_RetriesInterruptedUpload_AndRequeuesUploadedConfirmation()
    {
        var artifactRepo = new PendingArtifactRepository(_helper.DbManager);
        var outboxRepo = _helper.CreateOutboxRepository();
        var uploadingPath = ArtifactPath("uploading.txt");
        var uploadedPath = ArtifactPath("uploaded.txt");
        await File.WriteAllTextAsync(uploadingPath, "payload");
        await File.WriteAllTextAsync(uploadedPath, "payload");
        await artifactRepo.SaveAsync(CreatePendingArtifact("art_uploading", uploadingPath, status: ArtifactStatus.Uploading));
        await artifactRepo.SaveAsync(CreatePendingArtifact("art_uploaded_recover", uploadedPath, status: ArtifactStatus.Uploaded));

        var manager = CreateUploadManager(
            artifactRepo,
            outboxRepo,
            new RecordingArtifactContentUploader(PortalArtifactUploadOutcome.Ok()));

        await manager.RecoverUploadingAsync();

        (await artifactRepo.GetAsync("art_uploading"))!.Status.Should().Be(ArtifactStatus.RetryWait);
        var recoveredUploaded = await artifactRepo.GetAsync("art_uploaded_recover");
        recoveredUploaded!.Status.Should().Be(ArtifactStatus.Uploaded);
        recoveredUploaded.UploadedMessageId.Should().NotBeNullOrWhiteSpace();

        var outbox = await outboxRepo.GetReadyBatchAsync(10, _helper.Clock.UtcNow.AddMinutes(1));
        outbox.Should().ContainSingle(m => m.MessageType == PortalMessageTypes.ArtifactUploaded);
    }

    [Fact]
    public async Task ArtifactContentUploader_PutsBytesWithPortalProvidedHeaders()
    {
        var handler = new RecordingHttpMessageHandler(HttpStatusCode.OK);
        var uploader = new ArtifactContentUploader(new HttpClient(handler), NullLogger<ArtifactContentUploader>.Instance);
        var artifactPath = Path.Combine(_helper.TempDir, "put.txt");
        await File.WriteAllTextAsync(artifactPath, "payload");

        var outcome = await uploader.UploadAsync(
            new PortalArtifactUploadTarget(
                "https://portal.example/upload/upl_put",
                "PUT",
                "upl_put",
                new Dictionary<string, string> { ["x-upload-token"] = "token-1" }),
            artifactPath,
            "text/plain");

        outcome.Success.Should().BeTrue();
        handler.Method.Should().Be("PUT");
        handler.Uri!.ToString().Should().Be("https://portal.example/upload/upl_put");
        handler.Body.Should().Be("payload");
        handler.Headers.Should().ContainKey("x-upload-token");
    }

    [Fact]
    public async Task ArtifactConfirmedHandler_MarksLegacyArtifactConfirmed()
    {
        var artifactRepo = new PendingArtifactRepository(_helper.DbManager);
        var localPath = ArtifactPath("a.txt");
        await File.WriteAllTextAsync(localPath, "payload");
        await artifactRepo.SaveAsync(CreatePendingArtifact("art_confirm_1", localPath: localPath, status: ArtifactStatus.Uploaded));

        var handler = new ArtifactConfirmedHandler(
            artifactRepo,
            _helper.Clock,
            NullLogger<ArtifactConfirmedHandler>.Instance);

        var command = new InboxCommand
        {
            Id = 1,
            MessageId = "msg_art_confirm_1",
            CommandType = PortalMessageTypes.ArtifactConfirmed,
            PayloadJson = ProtocolJson.Serialize(new ArtifactConfirmedPayload
            {
                ArtifactId = "art_confirm_1",
                RemoteObjectId = "remote_1"
            }),
            ReceivedAtUtc = _helper.Clock.UtcNow,
            Status = InboxCommandStatus.Processing
        };

        var result = await handler.HandleAsync(command);

        result.Success.Should().BeTrue();
        result.Result.Should().Be("artifact_confirmed");
        var confirmed = await artifactRepo.GetAsync("art_confirm_1");
        confirmed!.Status.Should().Be(ArtifactStatus.Confirmed);
        confirmed.RemoteObjectId.Should().Be("remote_1");
        File.Exists(localPath).Should().BeFalse();
    }

    private ArtifactUploadManager CreateUploadManager(
        IPendingArtifactRepository artifactRepo,
        IOutboxRepository outboxRepo,
        IArtifactContentUploader uploader,
        ExecutionOptions? options = null)
    {
        return new ArtifactUploadManager(
            artifactRepo,
            uploader,
            CreatePublisher(outboxRepo),
            _helper.Clock,
            Options.Create(options ?? new ExecutionOptions()),
            NullLogger<ArtifactUploadManager>.Instance);
    }

    private OutboxMessagePublisher CreatePublisher(IOutboxRepository outbox)
    {
        return new OutboxMessagePublisher(outbox, _helper.CreateIdentityRepository(), _helper.Clock);
    }

    private PendingArtifactRecord CreatePendingArtifact(
        string artifactId,
        string localPath,
        ArtifactStatus status = ArtifactStatus.UploadUrlReceived,
        long sizeBytes = 7,
        string sha256 = PayloadSha,
        string uploadSessionId = "upl_test",
        DateTime? uploadExpiresAtUtc = null) => new()
    {
        ArtifactId = artifactId,
        ExecutionId = "exec_art",
        ExecutionAttemptId = "att_art",
        Name = Path.GetFileName(localPath),
        ContentType = "text/plain",
        SizeBytes = sizeBytes,
        Sha256 = sha256,
        LocalPath = localPath,
        Status = status,
        CreatedAtUtc = _helper.Clock.UtcNow,
        AvailableAtUtc = _helper.Clock.UtcNow,
        UploadSessionId = uploadSessionId,
        UploadUrl = $"https://upload.example/{artifactId}",
        UploadMethod = "PUT",
        UploadExpiresAtUtc = uploadExpiresAtUtc ?? _helper.Clock.UtcNow.AddMinutes(15)
    };

    private string ArtifactPath(string fileName)
    {
        var artifactsPath = Path.Combine(_helper.TempDir, "workspace", "artifacts");
        Directory.CreateDirectory(artifactsPath);
        return Path.Combine(artifactsPath, fileName);
    }

    private static JsonElement ResultElement(object value)
    {
        using var document = JsonDocument.Parse(ProtocolJson.Serialize(value));
        return document.RootElement.Clone();
    }

    private sealed class RecordingArtifactContentUploader : IArtifactContentUploader
    {
        private readonly Queue<PortalArtifactUploadOutcome> _outcomes;

        public RecordingArtifactContentUploader(params PortalArtifactUploadOutcome[] outcomes)
        {
            _outcomes = new Queue<PortalArtifactUploadOutcome>(outcomes);
        }

        public List<(PortalArtifactUploadTarget Target, string LocalPath, string ContentType)> Uploads { get; } = new();

        public Task<PortalArtifactUploadOutcome> UploadAsync(
            PortalArtifactUploadTarget target,
            string localPath,
            string contentType,
            CancellationToken ct = default)
        {
            Uploads.Add((target, localPath, contentType));
            return Task.FromResult(_outcomes.Count == 0 ? PortalArtifactUploadOutcome.Ok() : _outcomes.Dequeue());
        }
    }

    private sealed class RecordingHttpMessageHandler : HttpMessageHandler
    {
        private readonly HttpStatusCode _statusCode;

        public RecordingHttpMessageHandler(HttpStatusCode statusCode)
        {
            _statusCode = statusCode;
        }

        public string? Method { get; private set; }
        public Uri? Uri { get; private set; }
        public string? Body { get; private set; }
        public Dictionary<string, string> Headers { get; } = new(StringComparer.OrdinalIgnoreCase);

        protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            Method = request.Method.Method;
            Uri = request.RequestUri;
            if (request.Content is not null)
                Body = await request.Content.ReadAsStringAsync(cancellationToken);

            foreach (var header in request.Headers)
                Headers[header.Key] = string.Join(",", header.Value);

            return new HttpResponseMessage(_statusCode);
        }
    }
}
