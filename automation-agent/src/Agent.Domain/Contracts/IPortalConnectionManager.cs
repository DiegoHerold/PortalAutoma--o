using Biason.AutomationAgent.Domain.Enums;
using Biason.AutomationAgent.Domain.Models.Connections;

namespace Biason.AutomationAgent.Domain.Contracts;

/// <summary>
/// Conexão WebSocket única e persistente com o Portal (seção 11).
///
/// Uma única instância por processo do Agent — não abra um WebSocket por automação
/// nem por execução. Comandos e eventos de execução usam esta mesma conexão.
/// </summary>
public interface IPortalConnectionManager : IAsyncDisposable
{
    ConnectionState CurrentState { get; }

    /// <summary>Disparado a cada transição de estado da conexão.</summary>
    event Func<ConnectionState, ConnectionState, Task>? StateChanged;

    /// <summary>Disparado para cada mensagem válida recebida do Portal.</summary>
    event Func<InboundPortalMessage, Task>? MessageReceived;

    /// <summary>
    /// Inicia o laço de conexão em segundo plano: conecta, autentica, mantém viva,
    /// reconecta com backoff em caso de queda. Retorna quando <paramref name="ct"/>
    /// é cancelado ou <see cref="DisableAsync"/> é chamado.
    /// </summary>
    Task RunAsync(CancellationToken ct);

    /// <summary>
    /// Tenta enfileirar uma mensagem para envio imediato. Não bloqueia na rede — grava na
    /// fila de saída em memória e retorna. Se a conexão não estiver operacional (nenhum
    /// socket ativo agora) ou a fila estiver cheia, retorna <c>false</c> e a mensagem é
    /// descartada por esta camada — não há retenção nem retry aqui. Entrega garantida
    /// (persistir e reenviar depois) é responsabilidade do Outbox (Incremento 3), que deve
    /// persistir antes de chamar este método e decidir o que fazer quando ele retorna
    /// <c>false</c>.
    /// </summary>
    Task<bool> TrySendAsync(string messageType, object payload, string? correlationId = null, CancellationToken ct = default);

    /// <summary>Desabilita a conexão deliberadamente (não tenta reconectar até <see cref="EnableAsync"/>).</summary>
    Task DisableAsync(string reason, CancellationToken ct = default);

    Task EnableAsync(CancellationToken ct = default);

    ConnectionStatus GetStatus();
}

/// <summary>Mensagem recebida do Portal, já validada pelo <c>EnvelopeValidator</c>.</summary>
public sealed record InboundPortalMessage(
    string MessageId,
    string MessageType,
    string? CorrelationId,
    string? ExecutionId,
    string? ExecutionAttemptId,
    long? Sequence,
    object? Payload,
    DateTime ReceivedAtUtc);
