using System.ComponentModel.DataAnnotations;

namespace Biason.AutomationAgent.Domain.Configuration;

public sealed class ExecutionOptions
{
    public const string Section = "Execution";

    [Range(30, 86400)]
    public int DefaultTimeoutSeconds { get; init; } = 3600;

    [Range(5, 300)]
    public int GracefulShutdownSeconds { get; init; } = 30;

    [Range(1, 100)]
    public int MaxConcurrentExecutions { get; init; } = 5;

    [Range(60, 3600)]
    public int ReservationTimeoutSeconds { get; init; } = 300;

    /// <summary>
    /// Intervalo do serviço periódico que expira reservas TEMPORARY vencidas
    /// (Bloco 5.5, seção 11 — "não deixe expiração existir apenas no boot").
    /// </summary>
    [Range(5, 300)]
    public int ReservationExpirationPollIntervalSeconds { get; init; } = 15;

    /// <summary>
    /// Intervalo do serviço periódico que varre leases de execução (Bloco 5.5,
    /// seção 9/19) para pedir renovação dos que estão perto de expirar e
    /// marcar como perdidos os que passaram do prazo sem resposta do Portal.
    /// </summary>
    [Range(5, 300)]
    public int LeaseRenewalPollIntervalSeconds { get; init; } = 20;

    /// <summary>
    /// Janela antes do vencimento em que o Agent começa a pedir renovação
    /// (execution.lease_renew) e marca o lease como at_risk.
    /// </summary>
    [Range(5, 300)]
    public int LeaseRenewBeforeExpirySeconds { get; init; } = 60;

    /// <summary>
    /// Tolerância após o vencimento do lease antes de considerá-lo perdido
    /// (execution.lease_lost) — dá tempo para uma resposta atrasada do
    /// Portal chegar antes de cancelar a execução localmente.
    /// </summary>
    [Range(0, 120)]
    public int LeaseGraceSeconds { get; init; } = 30;

    [Range(5, 600)]
    public int ArtifactUploadPollIntervalSeconds { get; init; } = 30;

    [Range(1, 100)]
    public int ArtifactUploadBatchSize { get; init; } = 5;

    [Range(1, 20)]
    public int ArtifactUploadMaxAttempts { get; init; } = 5;

    [Range(5, 3600)]
    public int ArtifactRetryBaseDelaySeconds { get; init; } = 30;

    [Range(1, 10240)]
    public int ArtifactMaxSizeMb { get; init; } = 512;

    [Range(5, 86400)]
    public int ArtifactUploadTimeoutSeconds { get; init; } = 600;

    [Range(0, 8760)]
    public int ArtifactKeepConfirmedLocalHours { get; init; } = 0;

    public bool RequirePackageSignature { get; init; } = false; // true in production
}
