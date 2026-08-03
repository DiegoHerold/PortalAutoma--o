using Biason.AutomationAgent.Domain.Agents;

namespace Biason.AutomationAgent.Domain.Contracts;

/// <summary>
/// Guarda a credencial do Agent de forma protegida e expõe apenas metadados
/// não sensíveis para health checks e diagnóstico.
/// </summary>
public interface IAgentCredentialStore
{
    /// <summary>Grava a credencial protegida, substituindo a anterior.</summary>
    Task SaveAsync(AgentCredential credential, CancellationToken ct = default);

    /// <summary>Recupera a credencial. Null quando não há registro ou o blob é ilegível.</summary>
    Task<AgentCredential?> GetAsync(CancellationToken ct = default);

    /// <summary>Metadados seguros para exposição. Nunca contém o segredo.</summary>
    Task<AgentCredentialMetadata?> GetMetadataAsync(CancellationToken ct = default);

    /// <summary>Marca a credencial como revogada sem apagar o histórico de metadados.</summary>
    Task RevokeAsync(string reason, CancellationToken ct = default);

    /// <summary>Registra uso bem-sucedido, para observabilidade de rotação.</summary>
    Task TouchLastUsedAsync(CancellationToken ct = default);

    /// <summary>Remove definitivamente a credencial protegida.</summary>
    Task ClearAsync(CancellationToken ct = default);
}
