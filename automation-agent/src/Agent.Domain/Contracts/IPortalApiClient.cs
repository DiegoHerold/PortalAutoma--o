using Biason.AutomationAgent.Domain.Agents;

namespace Biason.AutomationAgent.Domain.Contracts;

/// <summary>
/// Cliente HTTPS do Portal, visto pelo domínio.
///
/// Deliberadamente livre de tipos de wire: os DTOs do protocolo vivem em
/// Agent.Protocol, que depende de Agent.Domain. Se este contrato usasse
/// aqueles DTOs a dependência ficaria circular. A implementação em
/// Agent.Infrastructure faz o mapeamento entre domínio e wire.
///
/// O canal de eventos e comandos é o WebSocket — não este cliente.
/// </summary>
public interface IPortalApiClient
{
    /// <summary>
    /// Executa o registro do Agent. Devolve resultado estruturado em vez de lançar,
    /// para o chamador distinguir rejeição definitiva de falha transitória.
    /// </summary>
    Task<PortalRegistrationOutcome> RegisterAsync(AgentRegistrationRequest request, CancellationToken ct = default);
}

/// <summary>Dados mínimos de identificação enviados no registro (seção 10).</summary>
public sealed record AgentRegistrationRequest(
    string InstallationId,
    string MachineId,
    string Hostname,
    string AgentVersion,
    string OperatingSystemName,
    string OperatingSystemArchitecture,
    string RegistrationToken);

/// <summary>Endereços devolvidos pelo Portal, que podem sobrescrever a configuração local.</summary>
public sealed record PortalEndpoints(string? WebSocketUrl, string? ApiBaseUrl);

/// <summary>Resultado bruto da chamada de registro, antes da política do serviço.</summary>
public sealed record PortalRegistrationOutcome(
    bool Success,
    string? AgentId = null,
    AgentCredential? Credential = null,
    PortalEndpoints? Endpoints = null,
    string? ReasonCode = null,
    string? Message = null,
    bool Retryable = false)
{
    public static PortalRegistrationOutcome Ok(string agentId, AgentCredential credential, PortalEndpoints? endpoints) =>
        new(true, agentId, credential, endpoints);

    /// <summary>Rejeição definitiva: repetir com o mesmo token não vai funcionar.</summary>
    public static PortalRegistrationOutcome Rejected(string reasonCode, string? message) =>
        new(false, ReasonCode: reasonCode, Message: message, Retryable: false);

    /// <summary>Falha transitória: rede, timeout, 5xx. Pode ser repetida com backoff.</summary>
    public static PortalRegistrationOutcome Transient(string reasonCode, string? message) =>
        new(false, ReasonCode: reasonCode, Message: message, Retryable: true);
}
