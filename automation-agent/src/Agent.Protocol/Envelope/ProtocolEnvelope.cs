using System.Text.Json.Serialization;

namespace Biason.AutomationAgent.Protocol.Envelope;

/// <summary>
/// Envelope versionado de toda mensagem trocada entre Portal e Agent.
///
/// Campos que não se aplicam a um tipo de mensagem são omitidos da serialização
/// (<see cref="JsonIgnoreCondition.WhenWritingNull"/>), conforme a seção 8 do contrato.
/// </summary>
public sealed class ProtocolEnvelope
{
    [JsonPropertyName("protocol_version")]
    public string ProtocolVersion { get; init; } = ProtocolConstants.CurrentVersion;

    /// <summary>Identificador globalmente único. Base da deduplicação em Outbox e Inbox.</summary>
    [JsonPropertyName("message_id")]
    public string MessageId { get; init; } = default!;

    [JsonPropertyName("message_type")]
    public string MessageType { get; init; } = default!;

    /// <summary>Sempre UTC.</summary>
    [JsonPropertyName("sent_at")]
    public DateTime SentAt { get; init; }

    [JsonPropertyName("agent_id")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public string? AgentId { get; init; }

    [JsonPropertyName("installation_id")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public string? InstallationId { get; init; }

    /// <summary>Identificador do processo do Agent. Permite ao Portal detectar reinicializações.</summary>
    [JsonPropertyName("agent_instance_id")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public string? AgentInstanceId { get; init; }

    [JsonPropertyName("execution_id")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public string? ExecutionId { get; init; }

    [JsonPropertyName("execution_attempt_id")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public string? ExecutionAttemptId { get; init; }

    /// <summary>
    /// Sequência monotônica por tentativa de execução. Usada para ordenação final —
    /// nunca dependa apenas de <see cref="SentAt"/> para ordenar eventos.
    /// </summary>
    [JsonPropertyName("sequence")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public long? Sequence { get; init; }

    [JsonPropertyName("correlation_id")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public string? CorrelationId { get; init; }

    [JsonPropertyName("causation_id")]
    [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
    public string? CausationId { get; init; }

    [JsonPropertyName("payload")]
    public object? Payload { get; init; }

    public static string NewMessageId() => $"msg_{Guid.NewGuid():N}";

    public static ProtocolEnvelope Create(
        string messageType,
        object? payload = null,
        string? agentId = null,
        string? installationId = null,
        string? agentInstanceId = null,
        string? executionId = null,
        string? executionAttemptId = null,
        long? sequence = null,
        string? correlationId = null,
        string? causationId = null,
        DateTime? sentAtUtc = null)
    {
        return new ProtocolEnvelope
        {
            MessageId = NewMessageId(),
            MessageType = messageType,
            SentAt = sentAtUtc ?? DateTime.UtcNow,
            AgentId = agentId,
            InstallationId = installationId,
            AgentInstanceId = agentInstanceId,
            ExecutionId = executionId,
            ExecutionAttemptId = executionAttemptId,
            Sequence = sequence,
            CorrelationId = correlationId,
            CausationId = causationId,
            Payload = payload
        };
    }
}
