using System.IO.Pipes;
using System.Runtime.Versioning;
using System.Security.AccessControl;
using System.Security.Cryptography;
using System.Security.Principal;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace Biason.AutomationAgent.ExecutionHost.Protocol;

/// <summary>
/// Canal local entre a automacao (SDK) e o ExecutionHost, descrito em
/// contracts/automation-events/v1/README.md. Um named pipe por tentativa, so do
/// usuario que roda a automacao, com token entregue por variavel de ambiente.
/// O ExecutionHost faz so a conferencia minima; quem valida o contrato inteiro e o Portal.
/// </summary>
[SupportedOSPlatform("windows")]
public sealed class AutomationEventsServer : IAsyncDisposable
{
    public const string EnvPipe = "AUTOMATION_EVENTS_PIPE";
    public const string EnvToken = "AUTOMATION_EVENTS_TOKEN";
    public const string ProtocolVersion = "automation-events/1";
    public const int MaxLineChars = 64 * 1024;
    private const int MaxPendingCommands = 32;
    // Com buffer zero cada escrita espera a automacao ler: um comando travaria o ExecutionHost.
    private const int PipeBufferBytes = 128 * 1024;
    private static readonly TimeSpan CommandWriteTimeout = TimeSpan.FromSeconds(5);

    private static readonly JsonSerializerOptions JsonOptions = new() { WriteIndented = false };

    private readonly Func<JsonElement, CancellationToken, Task> _forward;
    private readonly CancellationTokenSource _cts = new();
    private readonly SemaphoreSlim _writeLock = new(1, 1);
    private readonly Queue<JsonObject> _pendingCommands = new();
    private readonly object _stateLock = new();
    private StreamWriter? _writer;
    private Task? _loop;

    public AutomationEventsServer(string pipeName, string token, Func<JsonElement, CancellationToken, Task> forward)
    {
        PipeName = pipeName;
        Token = token;
        _forward = forward;
    }

    public string PipeName { get; }

    public string Token { get; }

    /// <summary>Maior sequencia ja repassada ao Agent. Reenvio de sequencia menor ou igual so recebe ACK.</summary>
    public long HighestSequence { get; private set; }

    public long ForwardedCount { get; private set; }

    public static AutomationEventsServer Create(string attemptId, Func<JsonElement, CancellationToken, Task> forward)
    {
        var safeAttempt = new string(attemptId.Where(char.IsLetterOrDigit).Take(40).ToArray());
        return new AutomationEventsServer($"biason-aut-ev-{safeAttempt}-{RandomHex(8)}", RandomHex(32), forward);
    }

    public void Start() => _loop = Task.Run(() => AcceptLoopAsync(_cts.Token));

    /// <summary>Comando para a automacao. Sem automacao conectada, fica guardado ate ela conectar.</summary>
    public async Task SendCommandAsync(string type, string? reason = null, CancellationToken ct = default)
    {
        var command = new JsonObject
        {
            ["protocol_version"] = ProtocolVersion,
            ["command_id"] = $"cmd_{RandomHex(12)}",
            ["type"] = type,
            ["issued_at"] = DateTime.UtcNow.ToString("O"),
        };
        if (!string.IsNullOrWhiteSpace(reason))
            command["motivo"] = reason;

        StreamWriter? writer;
        lock (_stateLock)
        {
            writer = _writer;
            if (writer is null)
            {
                if (_pendingCommands.Count >= MaxPendingCommands)
                    _pendingCommands.Dequeue();
                _pendingCommands.Enqueue(command);
                return;
            }
        }

        // Automacao que nao le o pipe nao pode segurar quem manda o comando (ex.: o
        // encerramento por tempo limite): passado o prazo, o comando volta para a fila.
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(ct);
        timeout.CancelAfter(CommandWriteTimeout);
        try
        {
            await WriteAsync(writer, new JsonObject { ["tipo"] = "comando", ["comando"] = command }, timeout.Token);
        }
        catch (Exception ex) when (ex is OperationCanceledException or IOException or ObjectDisposedException)
        {
            if (ct.IsCancellationRequested)
                throw;
            lock (_stateLock)
                _pendingCommands.Enqueue(command);
        }
    }

    private async Task AcceptLoopAsync(CancellationToken ct)
    {
        while (!ct.IsCancellationRequested)
        {
            await using var pipe = CreatePipe();
            try
            {
                await pipe.WaitForConnectionAsync(ct);
                await HandleConnectionAsync(pipe, ct);
            }
            catch (OperationCanceledException)
            {
                return;
            }
            catch (IOException)
            {
                // Automacao desconectou: o SDK reconecta e reenvia o que nao teve ACK.
            }
            finally
            {
                lock (_stateLock)
                    _writer = null;
            }
        }
    }

    private NamedPipeServerStream CreatePipe()
    {
        var security = new PipeSecurity();
        var user = WindowsIdentity.GetCurrent().User
                   ?? throw new InvalidOperationException("Usuario atual sem SID.");
        security.AddAccessRule(new PipeAccessRule(user, PipeAccessRights.FullControl, AccessControlType.Allow));
        return NamedPipeServerStreamAcl.Create(
            PipeName,
            PipeDirection.InOut,
            1,
            PipeTransmissionMode.Byte,
            PipeOptions.Asynchronous,
            PipeBufferBytes,
            PipeBufferBytes,
            security);
    }

    private async Task HandleConnectionAsync(NamedPipeServerStream pipe, CancellationToken ct)
    {
        using var reader = new StreamReader(pipe, new UTF8Encoding(false), detectEncodingFromByteOrderMarks: false, leaveOpen: true);
        var writer = new StreamWriter(pipe, new UTF8Encoding(false), leaveOpen: true) { AutoFlush = true };
        await using var _ = writer;

        var hello = await ReadBoundedLineAsync(reader, ct);
        if (!IsValidHello(hello))
        {
            await WriteAsync(writer, Error("token_invalido"), ct);
            return;
        }

        List<JsonObject> pending;
        lock (_stateLock)
        {
            _writer = writer;
            pending = [.. _pendingCommands];
            _pendingCommands.Clear();
        }

        await WriteAsync(writer, new JsonObject
        {
            ["tipo"] = "ok",
            ["protocol_version"] = ProtocolVersion,
            ["ultima_sequencia"] = HighestSequence,
        }, ct);
        foreach (var command in pending)
            await WriteAsync(writer, new JsonObject { ["tipo"] = "comando", ["comando"] = command }, ct);

        while (!ct.IsCancellationRequested && pipe.IsConnected)
        {
            string? line;
            try
            {
                line = await ReadBoundedLineAsync(reader, ct);
            }
            catch (InvalidDataException)
            {
                await WriteAsync(writer, Error("mensagem_grande_demais"), ct);
                return;
            }

            if (line is null)
                return;
            if (line.Length == 0)
                continue;

            await HandleMessageAsync(writer, line, ct);
        }
    }

    private async Task HandleMessageAsync(StreamWriter writer, string line, CancellationToken ct)
    {
        JsonElement message;
        try
        {
            using var document = JsonDocument.Parse(line);
            message = document.RootElement.Clone();
        }
        catch (JsonException)
        {
            await WriteAsync(writer, Error("json_invalido"), ct);
            return;
        }

        // Ping: o SDK le os comandos pendentes sem precisar de uma thread lendo o pipe.
        if (message.ValueKind == JsonValueKind.Object &&
            message.TryGetProperty("tipo", out var tipoPing) && tipoPing.GetString() == "ping")
        {
            await WriteAsync(writer, new JsonObject { ["tipo"] = "pong" }, ct);
            return;
        }

        if (message.ValueKind != JsonValueKind.Object ||
            !message.TryGetProperty("tipo", out var tipo) || tipo.GetString() != "evento" ||
            !message.TryGetProperty("evento", out var evento) || evento.ValueKind != JsonValueKind.Object)
        {
            await WriteAsync(writer, Error("mensagem_desconhecida"), ct);
            return;
        }

        if (!evento.TryGetProperty("protocol_version", out var version) || version.ValueKind != JsonValueKind.String ||
            version.GetString() != ProtocolVersion)
        {
            await WriteAsync(writer, Error("versao_incompativel"), ct);
            return;
        }

        if (!evento.TryGetProperty("sequence", out var sequenceElement) ||
            !sequenceElement.TryGetInt64(out var sequence) || sequence < 1 ||
            !evento.TryGetProperty("type", out var type) || type.ValueKind != JsonValueKind.String)
        {
            await WriteAsync(writer, Error("evento_invalido"), ct);
            return;
        }

        if (sequence > HighestSequence)
        {
            await _forward(evento, ct);
            HighestSequence = sequence;
            ForwardedCount++;
        }

        await WriteAsync(writer, new JsonObject { ["tipo"] = "ack", ["sequencia"] = sequence }, ct);
    }

    private bool IsValidHello(string? line)
    {
        if (string.IsNullOrEmpty(line))
            return false;
        try
        {
            using var document = JsonDocument.Parse(line);
            var root = document.RootElement;
            if (root.ValueKind != JsonValueKind.Object ||
                !root.TryGetProperty("tipo", out var tipo) || tipo.GetString() != "ola" ||
                !root.TryGetProperty("token", out var token) || token.ValueKind != JsonValueKind.String)
                return false;
            var sent = Encoding.UTF8.GetBytes(token.GetString() ?? "");
            var expected = Encoding.UTF8.GetBytes(Token);
            return CryptographicOperations.FixedTimeEquals(sent, expected);
        }
        catch (JsonException)
        {
            return false;
        }
    }

    /// <summary>Le uma linha sem deixar a automacao estourar a memoria do ExecutionHost.</summary>
    private static async Task<string?> ReadBoundedLineAsync(StreamReader reader, CancellationToken ct)
    {
        var builder = new StringBuilder();
        var buffer = new char[1];
        while (true)
        {
            var read = await reader.ReadAsync(buffer.AsMemory(), ct);
            if (read == 0)
                return builder.Length == 0 ? null : builder.ToString();
            var c = buffer[0];
            if (c == '\n')
                return builder.ToString().TrimEnd('\r');
            if (builder.Length >= MaxLineChars)
                throw new InvalidDataException("Linha acima do limite.");
            builder.Append(c);
        }
    }

    private async Task WriteAsync(StreamWriter writer, JsonObject message, CancellationToken ct)
    {
        var json = message.ToJsonString(JsonOptions);
        await _writeLock.WaitAsync(ct);
        try
        {
            await writer.WriteLineAsync(json.AsMemory(), ct);
        }
        finally
        {
            _writeLock.Release();
        }
    }

    private static JsonObject Error(string reason) => new() { ["tipo"] = "erro", ["motivo"] = reason };

    private static string RandomHex(int bytes) => Convert.ToHexString(RandomNumberGenerator.GetBytes(bytes)).ToLowerInvariant();

    public async ValueTask DisposeAsync()
    {
        await _cts.CancelAsync();
        if (_loop is not null)
        {
            try { await _loop; }
            catch (OperationCanceledException) { }
        }

        _cts.Dispose();
        _writeLock.Dispose();
    }
}
