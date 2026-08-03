using System.Collections.Concurrent;
using System.Threading.Channels;
using Biason.AutomationAgent.Domain.Contracts;

namespace Biason.AutomationAgent.IntegrationTests.Helpers;

/// <summary>
/// Dublê de <see cref="IWebSocketTransport"/> controlável em teste — sem rede real.
/// Cada chamada de <see cref="FakeWebSocketTransportFactory.Create"/> devolve uma nova
/// instância (como o transporte real faz), permitindo simular quedas seguidas de
/// reconexão bem-sucedida com um novo socket.
/// </summary>
public sealed class FakeWebSocketTransport : IWebSocketTransport
{
    private readonly Channel<TransportReceiveResult> _inbound =
        Channel.CreateUnbounded<TransportReceiveResult>(new UnboundedChannelOptions { SingleReader = true });

    private readonly ConcurrentQueue<string> _sent = new();

    /// <summary>Se definida, <see cref="ConnectAsync"/> lança esta exceção em vez de "conectar".</summary>
    public Exception? FailConnectWith { get; set; }

    public Uri? ConnectedUri { get; private set; }
    public IReadOnlyDictionary<string, string>? ConnectedHeaders { get; private set; }
    public IReadOnlyCollection<string> SentMessages => _sent;
    public bool IsOpen { get; private set; }
    public bool Disposed { get; private set; }
    public string? CloseReason { get; private set; }

    public Task ConnectAsync(Uri uri, IReadOnlyDictionary<string, string> headers, TimeSpan timeout, CancellationToken ct = default)
    {
        if (FailConnectWith is not null)
            return Task.FromException(FailConnectWith);

        ConnectedUri = uri;
        ConnectedHeaders = headers;
        IsOpen = true;
        return Task.CompletedTask;
    }

    public Task SendTextAsync(string message, CancellationToken ct = default)
    {
        _sent.Enqueue(message);
        return Task.CompletedTask;
    }

    public async Task<TransportReceiveResult> ReceiveAsync(CancellationToken ct = default)
    {
        return await _inbound.Reader.ReadAsync(ct);
    }

    public Task CloseAsync(string? reason, CancellationToken ct = default)
    {
        IsOpen = false;
        CloseReason = reason;
        return Task.CompletedTask;
    }

    /// <summary>Empurra uma mensagem de texto crua (JSON de envelope já serializado) como se viesse do Portal.</summary>
    public void EnqueueInboundText(string json) =>
        _inbound.Writer.TryWrite(TransportReceiveResult.TextMessage(json));

    /// <summary>Simula o Portal fechando o socket — o que deve derrubar o pump loop.</summary>
    public void EnqueueClose(string? reason = null) =>
        _inbound.Writer.TryWrite(TransportReceiveResult.Closed(reason));

    /// <summary>Simula um erro de transporte (ex.: RST de rede) chegando no ReceiveAsync.</summary>
    public void EnqueueError(Exception error) =>
        _inbound.Writer.TryWrite(TransportReceiveResult.Faulted(error));

    public ValueTask DisposeAsync()
    {
        Disposed = true;
        _inbound.Writer.TryComplete();
        return ValueTask.CompletedTask;
    }
}

/// <summary>
/// Fábrica controlável: por padrão cria um <see cref="FakeWebSocketTransport"/> novo por
/// chamada (documentando o mesmo contrato do transporte real — nunca reaproveitar socket
/// morto) e mantém referência de todas as instâncias criadas para asserção em teste.
/// </summary>
public sealed class FakeWebSocketTransportFactory : IWebSocketTransportFactory
{
    private readonly Func<int, FakeWebSocketTransport> _factory;
    private readonly List<FakeWebSocketTransport> _created = new();
    private int _createCount;

    public FakeWebSocketTransportFactory(Func<int, FakeWebSocketTransport>? factory = null)
    {
        _factory = factory ?? (_ => new FakeWebSocketTransport());
    }

    /// <summary>Todas as instâncias criadas até agora, na ordem de criação (1ª tentativa primeiro).</summary>
    public IReadOnlyList<FakeWebSocketTransport> Created
    {
        get { lock (_created) return _created.ToList(); }
    }

    public int CreateCount => _createCount;

    public IWebSocketTransport Create()
    {
        var attempt = Interlocked.Increment(ref _createCount);
        var transport = _factory(attempt);
        lock (_created) _created.Add(transport);
        return transport;
    }
}
