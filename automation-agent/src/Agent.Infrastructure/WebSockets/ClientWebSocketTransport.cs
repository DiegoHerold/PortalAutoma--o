using System.Net.WebSockets;
using System.Text;
using Biason.AutomationAgent.Domain.Contracts;

namespace Biason.AutomationAgent.Infrastructure.WebSockets;

/// <summary>
/// Implementação real de <see cref="IWebSocketTransport"/> sobre
/// <see cref="ClientWebSocket"/>. TLS é responsabilidade do próprio .NET quando o
/// endpoint é <c>wss://</c> — não há configuração adicional aqui além de validar o
/// esquema em <see cref="PortalOptions.RequireSecureTransport"/> (feito na configuração).
/// </summary>
public sealed class ClientWebSocketTransport : IWebSocketTransport
{
    private readonly ClientWebSocket _socket = new();
    private readonly byte[] _receiveBuffer = new byte[64 * 1024];
    private bool _disposed;

    public bool IsOpen => _socket.State == WebSocketState.Open;

    public async Task ConnectAsync(Uri uri, IReadOnlyDictionary<string, string> headers, TimeSpan timeout, CancellationToken ct = default)
    {
        foreach (var (name, value) in headers)
            _socket.Options.SetRequestHeader(name, value);

        // Ping/pong de protocolo (RFC 6455) fica a cargo do ClientWebSocket via
        // KeepAliveInterval — não expõe callback de pong, por isso o watchdog de
        // aplicação (PortalConnectionManager) cobre a detecção de silêncio total.
        _socket.Options.KeepAliveInterval = TimeSpan.FromSeconds(30);

        using var timeoutCts = new CancellationTokenSource(timeout);
        using var linked = CancellationTokenSource.CreateLinkedTokenSource(ct, timeoutCts.Token);

        try
        {
            await _socket.ConnectAsync(uri, linked.Token);
        }
        catch (OperationCanceledException) when (!ct.IsCancellationRequested && timeoutCts.IsCancellationRequested)
        {
            throw new TimeoutException($"Timeout ao conectar em {uri} após {timeout.TotalSeconds:F0}s.");
        }
    }

    public async Task SendTextAsync(string message, CancellationToken ct = default)
    {
        var bytes = Encoding.UTF8.GetBytes(message);
        await _socket.SendAsync(bytes, WebSocketMessageType.Text, endOfMessage: true, ct);
    }

    public async Task<TransportReceiveResult> ReceiveAsync(CancellationToken ct = default)
    {
        try
        {
            using var stream = new MemoryStream();
            WebSocketReceiveResult result;

            do
            {
                result = await _socket.ReceiveAsync(_receiveBuffer, ct);

                if (result.MessageType == WebSocketMessageType.Close)
                    return TransportReceiveResult.Closed(result.CloseStatusDescription);

                stream.Write(_receiveBuffer, 0, result.Count);
            }
            while (!result.EndOfMessage);

            var text = Encoding.UTF8.GetString(stream.ToArray());
            return TransportReceiveResult.TextMessage(text);
        }
        catch (OperationCanceledException)
        {
            throw;
        }
        catch (WebSocketException ex)
        {
            return TransportReceiveResult.Faulted(ex);
        }
    }

    public async Task CloseAsync(string? reason, CancellationToken ct = default)
    {
        if (_socket.State is WebSocketState.Open or WebSocketState.CloseReceived)
        {
            try
            {
                await _socket.CloseAsync(WebSocketCloseStatus.NormalClosure, reason ?? "closing", ct);
            }
            catch (WebSocketException)
            {
                // Peer já pode ter derrubado a conexão — não é um erro digno de propagar.
            }
        }
    }

    public async ValueTask DisposeAsync()
    {
        if (_disposed) return;
        _disposed = true;
        _socket.Dispose();
        await Task.CompletedTask;
    }
}

/// <summary>Cria uma instância nova de transporte a cada tentativa — nunca reaproveita um socket morto.</summary>
public sealed class ClientWebSocketTransportFactory : IWebSocketTransportFactory
{
    public IWebSocketTransport Create() => new ClientWebSocketTransport();
}
