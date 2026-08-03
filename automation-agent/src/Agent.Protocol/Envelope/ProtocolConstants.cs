namespace Biason.AutomationAgent.Protocol.Envelope;

public static class ProtocolConstants
{
    /// <summary>Versão do protocolo falada por esta build do Agent.</summary>
    public const string CurrentVersion = "1.0";

    /// <summary>
    /// Versão major mínima aceita. Mensagens com major diferente são rejeitadas
    /// explicitamente com <c>protocol.error</c> (seção 8: rejeição de versão incompatível).
    /// </summary>
    public const int SupportedMajorVersion = 1;

    /// <summary>
    /// Limite de payload de uma única mensagem no WebSocket. Artefatos grandes
    /// vão por HTTPS, nunca pelo socket (seção 20).
    /// </summary>
    public const int MaxMessageSizeBytes = 256 * 1024;

    /// <summary>Limite de mensagens em um lote enviado pelo Batch Sender.</summary>
    public const int MaxBatchMessages = 500;

    /// <summary>Tolerância de relógio ao validar <c>sent_at</c> contra o horário local.</summary>
    public static readonly TimeSpan MaxClockSkew = TimeSpan.FromMinutes(10);
}
