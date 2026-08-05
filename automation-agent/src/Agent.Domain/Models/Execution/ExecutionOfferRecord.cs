namespace Biason.AutomationAgent.Domain.Models.Execution;

public static class OfferDecision
{
    public const string Accepted = "accepted";
    public const string Rejected = "rejected";
}

/// <summary>
/// Linha persistida em <c>execution_offers</c> — trilha de auditoria e base
/// de idempotência de <c>execution.offer</c> (Bloco 5.5, seções 5-7).
/// </summary>
public sealed class ExecutionOfferRecord
{
    /// <summary>message_id do envelope que carregou a oferta (chave primária da tabela).</summary>
    public string OfferMessageId { get; init; } = default!;
    public string ExecutionId { get; init; } = default!;
    public string ExecutionAttemptId { get; init; } = default!;
    public string AutomationId { get; init; } = default!;
    public string? AutomationVersion { get; init; }
    public string? RuntimeId { get; init; }
    public string? RuntimeVersion { get; init; }
    public string Mode { get; init; } = "background";
    public string Pool { get; init; } = "background";
    public string OfferPayloadJson { get; init; } = "{}";
    public string Decision { get; init; } = default!;
    public string? ReasonCode { get; init; }
    public string? ReasonMessage { get; init; }
    public string? ReservationId { get; init; }
    public DateTime ReceivedAtUtc { get; init; }
    public DateTime? DecidedAtUtc { get; init; }
    public DateTime? ReservationExpiresAtUtc { get; init; }
}
