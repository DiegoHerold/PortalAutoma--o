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

    Task<PortalArtifactUploadTargetOutcome> RequestArtifactUploadAsync(
        PortalArtifactUploadRequest request,
        CancellationToken ct = default);

    Task<PortalArtifactUploadOutcome> UploadArtifactContentAsync(
        PortalArtifactUploadTarget target,
        string localPath,
        string contentType,
        CancellationToken ct = default);

    Task<PortalArtifactUploadOutcome> ConfirmArtifactUploadAsync(
        PortalArtifactUploadConfirmation confirmation,
        CancellationToken ct = default);
}

/// <summary>Dados mínimos de identificação enviados no registro (seção 10).</summary>
public sealed record AgentRegistrationRequest(
    string InstallationId,
    string MachineId,
    string? Name,
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

public sealed record PortalArtifactUploadRequest(
    string ArtifactId,
    string ExecutionId,
    string ExecutionAttemptId,
    string Name,
    string ContentType,
    long SizeBytes,
    string Sha256);

public sealed record PortalArtifactUploadTarget(
    string UploadUrl,
    string Method = "PUT",
    string? RemoteObjectId = null,
    IReadOnlyDictionary<string, string>? Headers = null);

public sealed record PortalArtifactUploadConfirmation(
    string ArtifactId,
    string ExecutionId,
    string ExecutionAttemptId,
    string Sha256,
    long SizeBytes,
    string? RemoteObjectId);

public sealed record PortalArtifactUploadTargetOutcome(
    bool Success,
    PortalArtifactUploadTarget? Target = null,
    string? ReasonCode = null,
    string? Message = null,
    bool Retryable = true)
{
    public static PortalArtifactUploadTargetOutcome Ok(PortalArtifactUploadTarget target) =>
        new(true, target);

    public static PortalArtifactUploadTargetOutcome Failed(string reasonCode, string? message, bool retryable = true) =>
        new(false, null, reasonCode, message, retryable);
}

public sealed record PortalArtifactUploadOutcome(
    bool Success,
    string? ReasonCode = null,
    string? Message = null,
    bool Retryable = true)
{
    public static PortalArtifactUploadOutcome Ok() => new(true);

    public static PortalArtifactUploadOutcome Failed(string reasonCode, string? message, bool retryable = true) =>
        new(false, reasonCode, message, retryable);
}
