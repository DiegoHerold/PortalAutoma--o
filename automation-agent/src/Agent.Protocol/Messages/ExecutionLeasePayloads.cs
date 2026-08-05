using System.Text.Json.Serialization;

namespace Biason.AutomationAgent.Protocol.Messages;

/// <summary>
/// Payloads do ciclo de lease de execução (Bloco 5.5, seção 9/19). Não há
/// contrato JSON publicado em contracts/ para essas mensagens (apenas
/// execution.commit, que carrega a concessão inicial do lease em
/// lease_id/lease_expires_at — ver ExecutionCommitPayloads.cs); os nomes de
/// campo abaixo seguem a mesma convenção snake_case das demais mensagens do
/// protocolo (docs/protocol.md, PortalMessageTypes).
/// </summary>

/// <summary>execution.lease_renew (Agent -&gt; Portal): pede renovação de um lease perto de expirar.</summary>
public sealed class LeaseRenewRequestPayload
{
    [JsonPropertyName("lease_id")]
    public string LeaseId { get; init; } = default!;

    [JsonPropertyName("execution_attempt_id")]
    public string ExecutionAttemptId { get; init; } = default!;

    [JsonPropertyName("renewal_sequence")]
    public long RenewalSequence { get; init; }

    [JsonPropertyName("running")]
    public bool Running { get; init; } = true;

    [JsonPropertyName("observed_at")]
    public DateTime? ObservedAt { get; init; }
}

/// <summary>execution.lease_lost (Agent -&gt; Portal): o Agent desistiu de renovar e vai cancelar a execução localmente.</summary>
public sealed class LeaseLostPayload
{
    [JsonPropertyName("lease_id")]
    public string LeaseId { get; init; } = default!;

    [JsonPropertyName("execution_attempt_id")]
    public string ExecutionAttemptId { get; init; } = default!;

    [JsonPropertyName("reason")]
    public string Reason { get; init; } = default!;
}

/// <summary>
/// execution.lease_renewed / execution.lease_granted (Portal -&gt; Agent):
/// mesma forma de payload nos dois casos — o Portal concede um novo prazo
/// para o lease (renovação de um existente, ou concessão avulsa fora do
/// commit). Tratados de forma idêntica pelo ExecutionLeaseManager.
/// </summary>
public sealed class LeaseGrantPayload
{
    [JsonPropertyName("lease_id")]
    public string LeaseId { get; init; } = default!;

    [JsonPropertyName("execution_attempt_id")]
    public string ExecutionAttemptId { get; init; } = default!;

    [JsonPropertyName("expires_at")]
    public DateTime ExpiresAt { get; init; }
}

/// <summary>execution.lease_expired (Portal -&gt; Agent): o Portal encerrou o lease; a execução não pode continuar.</summary>
public sealed class LeaseExpiredNoticePayload
{
    [JsonPropertyName("lease_id")]
    public string LeaseId { get; init; } = default!;

    [JsonPropertyName("execution_attempt_id")]
    public string ExecutionAttemptId { get; init; } = default!;

    [JsonPropertyName("reason")]
    public string? Reason { get; init; }
}
