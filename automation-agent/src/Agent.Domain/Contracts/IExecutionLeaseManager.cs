namespace Biason.AutomationAgent.Domain.Contracts;

/// <summary>
/// Dono da lógica de estado dos leases de execução (Bloco 5.5, seção 9/19):
/// pedir renovação antes do vencimento, aplicar respostas do Portal
/// (renovado/concedido/expirado), marcar como perdido e cancelar a execução
/// local quando o Portal não responde a tempo, e reconciliar no boot.
/// Não fala diretamente com a conexão WebSocket — publica via Outbox (mesma
/// garantia de entrega at-least-once dos demais eventos de execução) e é
/// alimentado por quem recebe as mensagens inbound (ver
/// LeaseMessageListenerService).
/// </summary>
public interface IExecutionLeaseManager
{
    /// <summary>
    /// Varre leases não-finais (active/at_risk): pede renovação dos que
    /// entraram na janela de pré-vencimento e marca como perdidos (e cancela
    /// a execução associada) os que passaram do vencimento + tolerância sem
    /// resposta do Portal. Chamado periodicamente por LeaseRenewalService.
    /// </summary>
    Task RenewDueLeasesAsync(CancellationToken ct = default);

    /// <summary>Aplica execution.lease_renewed ou execution.lease_granted (mesmo tratamento nos dois casos).</summary>
    Task HandleLeaseGrantedAsync(string leaseId, string executionAttemptId, DateTime expiresAtUtc, CancellationToken ct = default);

    /// <summary>Aplica execution.lease_expired: o Portal encerrou o lease: marca perdido e cancela a execução local.</summary>
    Task HandleLeaseExpiredAsync(string leaseId, string executionAttemptId, string? reason, CancellationToken ct = default);

    /// <summary>
    /// Reconciliação de boot (Bloco 5.5, seção 19): leases não-finais cujo
    /// prazo (+ tolerância) já passou enquanto o Agent estava fora do ar
    /// entram direto em Lost, sem esperar o primeiro ciclo do
    /// LeaseRenewalService.
    /// </summary>
    Task ReconcileOnBootAsync(CancellationToken ct = default);
}
