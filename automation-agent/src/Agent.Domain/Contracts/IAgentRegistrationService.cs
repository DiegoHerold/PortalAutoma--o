using Biason.AutomationAgent.Domain.Agents;

namespace Biason.AutomationAgent.Domain.Contracts;

/// <summary>
/// Fluxo de registro do Agent no Portal (seção 10).
/// Idempotente: se já houver agent_id e credencial válida, não registra de novo.
/// </summary>
public interface IAgentRegistrationService
{
    /// <summary>
    /// Garante que o Agent esteja registrado. Seguro para chamar em toda inicialização —
    /// não gera novo registro quando já existe um válido.
    /// </summary>
    Task<RegistrationResult> EnsureRegisteredAsync(CancellationToken ct = default);

    /// <summary>Força novo registro, descartando a credencial atual. Uso administrativo.</summary>
    Task<RegistrationResult> ForceRegisterAsync(CancellationToken ct = default);

    /// <summary>True quando existem agent_id e credencial não revogada nem expirada.</summary>
    Task<bool> IsRegisteredAsync(CancellationToken ct = default);
}
