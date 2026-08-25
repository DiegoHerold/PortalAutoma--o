using Biason.AutomationAgent.Domain.Agents;
using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Contracts;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace Biason.AutomationAgent.Application.Registration;

/// <summary>
/// Orquestra o registro do Agent no Portal (seção 10).
///
/// Idempotência é o requisito central: <see cref="EnsureRegisteredAsync"/> roda em
/// toda inicialização e não pode gerar um novo registro quando já existe um válido.
/// A checagem combina agent_id persistido + credencial recuperável e não revogada.
/// </summary>
public sealed class AgentRegistrationService : IAgentRegistrationService
{
    private readonly IAgentIdentityService _identity;
    private readonly IAgentCredentialStore _credentials;
    private readonly IPortalApiClient _portal;
    private readonly IOsInfoCollector _osInfo;
    private readonly PortalOptions _portalOptions;
    private readonly AgentOptions _agentOptions;
    private readonly IClock _clock;
    private readonly ILogger<AgentRegistrationService> _logger;

    private readonly SemaphoreSlim _gate = new(1, 1);

    public AgentRegistrationService(
        IAgentIdentityService identity,
        IAgentCredentialStore credentials,
        IPortalApiClient portal,
        IOsInfoCollector osInfo,
        IOptions<PortalOptions> portalOptions,
        IOptions<AgentOptions> agentOptions,
        IClock clock,
        ILogger<AgentRegistrationService> logger)
    {
        _identity = identity;
        _credentials = credentials;
        _portal = portal;
        _osInfo = osInfo;
        _portalOptions = portalOptions.Value;
        _agentOptions = agentOptions.Value;
        _clock = clock;
        _logger = logger;
    }

    public async Task<RegistrationResult> EnsureRegisteredAsync(CancellationToken ct = default)
    {
        if (!_portalOptions.Enabled)
        {
            _logger.LogInformation("Integração com o Portal desabilitada; registro ignorado.");
            return RegistrationResult.NotConfigured();
        }

        await _gate.WaitAsync(ct);
        try
        {
            var identity = await _identity.GetOrCreateIdentityAsync(ct);

            if (await HasValidRegistrationAsync(identity, ct))
            {
                _logger.LogInformation("Agent já registrado (agent_id={AgentId}); nenhum novo registro necessário.",
                    identity.AgentId);
                return RegistrationResult.AlreadyRegistered(identity.AgentId!);
            }

            return await RegisterInternalAsync(ct);
        }
        finally
        {
            _gate.Release();
        }
    }

    public async Task<RegistrationResult> ForceRegisterAsync(CancellationToken ct = default)
    {
        if (!_portalOptions.Enabled)
            return RegistrationResult.NotConfigured();

        await _gate.WaitAsync(ct);
        try
        {
            _logger.LogWarning("Registro forçado solicitado; credencial atual será descartada.");
            await _credentials.ClearAsync(ct);
            return await RegisterInternalAsync(ct);
        }
        finally
        {
            _gate.Release();
        }
    }

    public async Task<bool> IsRegisteredAsync(CancellationToken ct = default)
    {
        var identity = await _identity.GetIdentityAsync(ct);
        return identity is not null && await HasValidRegistrationAsync(identity, ct);
    }

    /// <summary>
    /// Registro só é considerado válido quando há agent_id persistido E credencial
    /// legível, não revogada e não expirada. Faltando qualquer parte, registramos de novo.
    /// </summary>
    private async Task<bool> HasValidRegistrationAsync(Domain.Identity.AgentIdentity identity, CancellationToken ct)
    {
        if (!identity.IsRegistered)
            return false;

        var metadata = await _credentials.GetMetadataAsync(ct);
        if (metadata is null)
        {
            _logger.LogWarning("agent_id presente mas sem credencial armazenada; novo registro necessário.");
            return false;
        }

        if (metadata.IsRevoked)
        {
            _logger.LogWarning("Credencial revogada em {RevokedAt}; novo registro necessário.", metadata.RevokedAtUtc);
            return false;
        }

        if (metadata.ExpiresAtUtc is not null && metadata.ExpiresAtUtc <= _clock.UtcNow)
        {
            _logger.LogWarning("Credencial expirada em {ExpiresAt}; novo registro necessário.", metadata.ExpiresAtUtc);
            return false;
        }

        // Confirma que o blob é realmente desprotegível nesta máquina.
        var credential = await _credentials.GetAsync(ct);
        if (credential is null)
        {
            _logger.LogWarning("Credencial existe em metadados mas não pôde ser desprotegida; novo registro necessário.");
            return false;
        }

        var rotationThreshold = TimeSpan.FromDays(_portalOptions.CredentialRotationThresholdDays);
        if (credential.NeedsRotation(_clock.UtcNow, rotationThreshold))
        {
            // Ainda válida — apenas sinalizamos. A rotação em si é da Fase 4.
            _logger.LogInformation(
                "Credencial expira em {ExpiresAt}, dentro da janela de rotação de {Days} dias.",
                credential.ExpiresAtUtc, _portalOptions.CredentialRotationThresholdDays);
        }

        return true;
    }

    private async Task<RegistrationResult> RegisterInternalAsync(CancellationToken ct)
    {
        var token = _portalOptions.RegistrationToken;
        if (string.IsNullOrWhiteSpace(token))
        {
            _logger.LogWarning("Sem token de registro configurado; o Agent seguirá apenas local.");
            return RegistrationResult.NotConfigured();
        }

        var identity = await _identity.GetOrCreateIdentityAsync(ct);
        var os = _osInfo.Collect();

        var request = new AgentRegistrationRequest(
            InstallationId: identity.InstallationId,
            MachineId: identity.MachineId,
            Name: _agentOptions.Name,
            Hostname: Environment.MachineName,
            AgentVersion: _agentOptions.Version,
            OperatingSystemName: os.Name,
            OperatingSystemArchitecture: os.Architecture,
            RegistrationToken: token);

        var outcome = await _portal.RegisterAsync(request, ct);

        if (!outcome.Success)
        {
            var result = outcome.Retryable
                ? RegistrationResult.Failed(outcome.ReasonCode ?? "REGISTRATION_FAILED", outcome.Message)
                : RegistrationResult.Rejected(outcome.ReasonCode ?? "REGISTRATION_FAILED", outcome.Message);

            _logger.LogError(
                "Registro no Portal falhou: reason={Reason}, retryable={Retryable}, message={Message}",
                result.ReasonCode, result.Retryable, result.Message);

            return result;
        }

        // Ordem importa: grava credencial antes do agent_id. Se o processo morrer
        // no meio, a próxima inicialização vê "sem agent_id" e registra de novo,
        // em vez de ficar com agent_id sem credencial utilizável.
        await _credentials.SaveAsync(outcome.Credential!, ct);
        await _identity.UpdateAgentIdAsync(outcome.AgentId!, ct);

        _logger.LogInformation("Agent registrado com sucesso (agent_id={AgentId})", outcome.AgentId);
        return RegistrationResult.Registered(outcome.AgentId!);
    }
}
