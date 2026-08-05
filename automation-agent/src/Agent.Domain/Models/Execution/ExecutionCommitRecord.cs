namespace Biason.AutomationAgent.Domain.Models.Execution;

/// <summary>
/// Linha persistida em <c>execution_commits</c> — trilha de auditoria e base
/// de idempotência de <c>execution.commit</c> (Bloco 5.5, seções 13-17).
/// A unicidade real contra duplicação é garantida no schema por
/// <c>idx_execution_commits_attempt</c> (um commit aceito por tentativa).
/// </summary>
public sealed class ExecutionCommitRecord
{
    /// <summary>message_id do envelope que carregou o commit (chave primária da tabela).</summary>
    public string CommitMessageId { get; init; } = default!;
    public string ExecutionId { get; init; } = default!;
    public string ExecutionAttemptId { get; init; } = default!;
    public string? ReservationId { get; init; }
    public bool Accepted { get; init; }
    public string? RejectionReason { get; init; }
    public DateTime ReceivedAtUtc { get; init; }
    public DateTime? ProcessedAtUtc { get; init; }
}
