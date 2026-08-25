using System.IO.Pipes;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using Biason.AutomationAgent.Application.Messaging;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Domain.Models.Execution;
using Biason.AutomationAgent.Protocol.Messages;
using Microsoft.Extensions.Logging;
using ExecutionContext = Biason.AutomationAgent.Domain.Models.Execution.ExecutionContext;

namespace Biason.AutomationAgent.Application.Execution;

public sealed class ExecutionHostPipePump
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true
    };

    private readonly IExecutionEventRepository _events;
    private readonly OutboxMessagePublisher _outbox;
    private readonly ExecutionAttemptSequenceTracker _sequences;
    private readonly IClock _clock;
    private readonly ILogger<ExecutionHostPipePump> _logger;

    public ExecutionHostPipePump(
        IExecutionEventRepository events,
        OutboxMessagePublisher outbox,
        ExecutionAttemptSequenceTracker sequences,
        IClock clock,
        ILogger<ExecutionHostPipePump> logger)
    {
        _events = events;
        _outbox = outbox;
        _sequences = sequences;
        _clock = clock;
        _logger = logger;
    }

    public IAsyncDisposable Start(ExecutionContext context, string pipeName, CancellationToken ct = default)
    {
        var cts = CancellationTokenSource.CreateLinkedTokenSource(ct);
        var pipe = CreatePipe(pipeName);
        var task = Task.Run(() => PumpAsync(context, pipe, cts.Token), CancellationToken.None);
        return new PipePumpSession(pipeName, pipe, cts, task, _logger);
    }

    private static NamedPipeServerStream CreatePipe(string pipeName)
    {
        return new NamedPipeServerStream(
            pipeName,
            PipeDirection.InOut,
            1,
            PipeTransmissionMode.Byte,
            PipeOptions.Asynchronous);
    }

    private async Task PumpAsync(ExecutionContext context, NamedPipeServerStream pipe, CancellationToken ct)
    {
        try
        {
            await pipe.WaitForConnectionAsync(ct);
            using var reader = new StreamReader(pipe, Encoding.UTF8, detectEncodingFromByteOrderMarks: false, leaveOpen: true);

            while (!ct.IsCancellationRequested && pipe.IsConnected)
            {
                var line = await reader.ReadLineAsync(ct);
                if (line is null)
                    break;

                await HandleLineAsync(context, line, ct);
            }
        }
        catch (OperationCanceledException) { }
        catch (IOException ex)
        {
            _logger.LogDebug(ex, "ExecutionHost pipe closed for {ExecutionId}/{AttemptId}.", context.ExecutionId, context.AttemptId);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "ExecutionHost pipe pump failed for {ExecutionId}/{AttemptId}.", context.ExecutionId, context.AttemptId);
        }
    }

    private async Task HandleLineAsync(ExecutionContext context, string line, CancellationToken ct)
    {
        HostPipeMessage? message;
        try
        {
            message = JsonSerializer.Deserialize<HostPipeMessage>(line, JsonOptions);
        }
        catch (JsonException ex)
        {
            _logger.LogWarning(ex, "Invalid ExecutionHost pipe message for {ExecutionId}/{AttemptId}.", context.ExecutionId, context.AttemptId);
            return;
        }

        if (message is null || string.IsNullOrWhiteSpace(message.MessageType))
            return;

        var portalType = ToPortalMessageType(message.MessageType);
        if (portalType is null)
            return;

        var payload = NormalizePayload(portalType, message.Payload?.Clone() ?? EmptyPayload());
        var sequence = _sequences.Next(context.AttemptId);
        var occurredAt = message.SentAtUtc == default ? _clock.UtcNow : message.SentAtUtc.ToUniversalTime();

        await _events.SaveAsync(new ExecutionEvent
        {
            ExecutionId = context.ExecutionId,
            AttemptId = context.AttemptId,
            EventType = portalType,
            Message = TryReadMessage(payload),
            DataJson = payload.GetRawText(),
            OccurredAtUtc = occurredAt
        }, ct);

        await _outbox.EnqueueAsync(
            portalType,
            payload,
            executionId: context.ExecutionId,
            executionAttemptId: context.AttemptId,
            sequence: sequence,
            ct: ct);
    }

    private static JsonElement EmptyPayload()
    {
        using var document = JsonDocument.Parse("{}");
        return document.RootElement.Clone();
    }

    private static string? ToPortalMessageType(string hostMessageType) => hostMessageType switch
    {
        PortalMessageTypes.ExecutionLog => PortalMessageTypes.ExecutionLog,
        PortalMessageTypes.ExecutionProgress => PortalMessageTypes.ExecutionProgress,
        PortalMessageTypes.ExecutionMetric => PortalMessageTypes.ExecutionMetric,
        _ => null
    };

    private static string? TryReadMessage(JsonElement payload)
    {
        if (payload.ValueKind != JsonValueKind.Object)
            return null;

        if (payload.TryGetProperty("message", out var message) && message.ValueKind == JsonValueKind.String)
            return message.GetString();

        if (payload.TryGetProperty("name", out var name) && name.ValueKind == JsonValueKind.String)
            return name.GetString();

        return null;
    }

    private static JsonElement NormalizePayload(string portalType, JsonElement payload)
    {
        if (portalType != PortalMessageTypes.ExecutionMetric || payload.ValueKind != JsonValueKind.Object)
            return payload;

        var values = JsonSerializer.Deserialize<Dictionary<string, object?>>(payload.GetRawText(), JsonOptions)
                     ?? new Dictionary<string, object?>(StringComparer.Ordinal);

        if (!values.ContainsKey("metric_name") && values.TryGetValue("name", out var name))
            values["metric_name"] = name;

        values.Remove("name");
        if (!values.ContainsKey("metric_type"))
            values["metric_type"] = "gauge";

        return JsonSerializer.SerializeToElement(values, JsonOptions);
    }

    private sealed class PipePumpSession : IAsyncDisposable
    {
        private readonly string _pipeName;
        private readonly NamedPipeServerStream _pipe;
        private readonly CancellationTokenSource _cts;
        private readonly Task _task;
        private readonly ILogger _logger;

        public PipePumpSession(string pipeName, NamedPipeServerStream pipe, CancellationTokenSource cts, Task task, ILogger logger)
        {
            _pipeName = pipeName;
            _pipe = pipe;
            _cts = cts;
            _task = task;
            _logger = logger;
        }

        public async ValueTask DisposeAsync()
        {
            _cts.Cancel();
            try { _pipe.Dispose(); } catch { }

            try { await _task; }
            catch (OperationCanceledException) { }
            catch (Exception ex) { _logger.LogDebug(ex, "ExecutionHost pipe session {PipeName} ended with an error.", _pipeName); }

            _cts.Dispose();
        }
    }

    private sealed class HostPipeMessage
    {
        [JsonPropertyName("message_type")]
        public string MessageType { get; init; } = "";

        [JsonPropertyName("sent_at")]
        public DateTime SentAtUtc { get; init; }

        [JsonPropertyName("sequence")]
        public long Sequence { get; init; }

        [JsonPropertyName("payload")]
        public JsonElement? Payload { get; init; }
    }
}
