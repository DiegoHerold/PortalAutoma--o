using System.IO.Pipes;
using System.Text;
using System.Text.Json;

namespace Biason.AutomationAgent.ExecutionHost.Protocol;

/// <summary>
/// Named pipe client for sending structured messages to the Agent Service.
/// Each message is a JSON line terminated by newline.
/// </summary>
public sealed class PipeClient : IAsyncDisposable
{
    private readonly NamedPipeClientStream _pipe;
    private readonly StreamWriter _writer;
    private readonly string _executionId;
    private readonly string _attemptId;
    private long _sequence;

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        WriteIndented = false
    };

    public PipeClient(string pipeName, string executionId, string attemptId)
    {
        _executionId = executionId;
        _attemptId = attemptId;
        _pipe = new NamedPipeClientStream(".", pipeName, PipeDirection.InOut, PipeOptions.Asynchronous);
        _writer = new StreamWriter(_pipe, Encoding.UTF8, leaveOpen: true) { AutoFlush = true };
    }

    public async Task ConnectAsync(int timeoutMs = 10000, CancellationToken ct = default)
    {
        await _pipe.ConnectAsync(timeoutMs, ct);
    }

    public bool IsConnected => _pipe.IsConnected;

    public async Task SendAsync(string messageType, object? payload = null, CancellationToken ct = default)
    {
        var msg = new HostMessage
        {
            MessageType = messageType,
            ExecutionId = _executionId,
            AttemptId = _attemptId,
            Sequence = Interlocked.Increment(ref _sequence),
            SentAtUtc = DateTime.UtcNow,
            Payload = payload
        };

        var json = JsonSerializer.Serialize(msg, JsonOptions);
        await _writer.WriteLineAsync(json.AsMemory(), ct);
    }

    public async Task SendLogAsync(string level, string message, CancellationToken ct = default)
    {
        await SendAsync(MessageTypes.Log, new { level, message }, ct);
    }

    public async Task SendProgressAsync(int current, int total, string? message = null, CancellationToken ct = default)
    {
        await SendAsync(MessageTypes.Progress, new { current, total, message }, ct);
    }

    public async Task SendMetricAsync(string name, double value, CancellationToken ct = default)
    {
        await SendAsync(MessageTypes.Metric, new { name, value }, ct);
    }

    public async Task<string?> ReadMessageAsync(CancellationToken ct = default)
    {
        if (!_pipe.IsConnected) return null;

        var reader = new StreamReader(_pipe, Encoding.UTF8, leaveOpen: true);
        try
        {
            return await reader.ReadLineAsync(ct);
        }
        catch
        {
            return null;
        }
    }

    public async ValueTask DisposeAsync()
    {
        await _writer.DisposeAsync();
        await _pipe.DisposeAsync();
    }
}
