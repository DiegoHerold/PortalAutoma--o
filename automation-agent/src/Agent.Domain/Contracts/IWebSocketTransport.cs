namespace Biason.AutomationAgent.Domain.Contracts;

/// <summary>
/// Abstração de baixo nível sobre o WebSocket, para permitir testar
/// <c>PortalConnectionManager</c> (reconexão, backoff, fila) sem rede real.
/// A implementação real envolve <see cref="System.Net.WebSockets.ClientWebSocket"/>.
/// </summary>
public interface IWebSocketTransport : IAsyncDisposable
{
    bool IsOpen { get; }

    Task ConnectAsync(Uri uri, IReadOnlyDictionary<string, string> headers, TimeSpan timeout, CancellationToken ct = default);

    Task SendTextAsync(string message, CancellationToken ct = default);

    /// <summary>Bloqueia até a próxima mensagem, fechamento ou cancelamento.</summary>
    Task<TransportReceiveResult> ReceiveAsync(CancellationToken ct = default);

    Task CloseAsync(string? reason, CancellationToken ct = default);
}

public enum TransportMessageKind
{
    Text,
    Closed,
    Error
}

public sealed record TransportReceiveResult(
    TransportMessageKind Kind,
    string? Text = null,
    string? CloseReason = null,
    Exception? Error = null)
{
    public static TransportReceiveResult TextMessage(string text) => new(TransportMessageKind.Text, Text: text);
    public static TransportReceiveResult Closed(string? reason) => new(TransportMessageKind.Closed, CloseReason: reason);
    public static TransportReceiveResult Faulted(Exception error) => new(TransportMessageKind.Error, Error: error);
}

/// <summary>Cria uma nova instância de transporte a cada tentativa de conexão.</summary>
public interface IWebSocketTransportFactory
{
    IWebSocketTransport Create();
}
