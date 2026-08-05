namespace Biason.AutomationAgent.Domain.Models.Execution;

/// <summary>Bloco 5.5, seção 9 / Bloco 6, seção 9 — estados do lease de execução.</summary>
public static class LeaseState
{
    public const string Active = "active";
    public const string AtRisk = "at_risk";
    public const string Expired = "expired";
    public const string Lost = "lost";
    public const string Released = "released";
}

/// <summary>
/// Linha persistida em <c>execution_leases</c>. Diferente do lock de desktop,
/// este lease representa a concessão do Portal para a execução continuar —
/// concedido junto com o commit (lease_id/lease_expires_at no payload), não
/// solicitado pelo Agent.
/// </summary>
public sealed class ExecutionLeaseRecord
{
    public string LeaseId { get; init; } = default!;
    public string ExecutionId { get; init; } = default!;
    public string ExecutionAttemptId { get; init; } = default!;
    public string State { get; set; } = LeaseState.Active;
    public DateTime GrantedAtUtc { get; init; }
    public DateTime ExpiresAtUtc { get; set; }
    public DateTime? LastRenewedAtUtc { get; set; }
    public int RenewAttemptCount { get; set; }
    public DateTime? LostAtUtc { get; set; }
    public string? LostReason { get; set; }
}
