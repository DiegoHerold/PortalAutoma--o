using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using Biason.AutomationAgent.Domain.Agents;
using Biason.AutomationAgent.Domain.Configuration;
using Biason.AutomationAgent.Domain.Contracts;
using Biason.AutomationAgent.Protocol.Registration;
using Biason.AutomationAgent.Protocol.Serialization;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace Biason.AutomationAgent.Infrastructure.Http;

/// <summary>
/// Implementação HTTPS do <see cref="IPortalApiClient"/>.
/// Faz o mapeamento entre os tipos de domínio e os DTOs de wire do protocolo.
/// </summary>
public sealed class PortalApiClient : IPortalApiClient
{
    private readonly HttpClient _http;
    private readonly PortalOptions _options;
    private readonly IClock _clock;
    private readonly ILogger<PortalApiClient> _logger;

    public PortalApiClient(
        HttpClient http,
        IOptions<PortalOptions> options,
        IClock clock,
        ILogger<PortalApiClient> logger)
    {
        _http = http;
        _options = options.Value;
        _clock = clock;
        _logger = logger;
    }

    public async Task<PortalRegistrationOutcome> RegisterAsync(
        AgentRegistrationRequest request,
        CancellationToken ct = default)
    {
        var wire = new RegistrationRequest
        {
            InstallationId = request.InstallationId,
            MachineId = request.MachineId,
            Hostname = request.Hostname,
            AgentVersion = request.AgentVersion,
            OperatingSystem = new RegistrationOsInfo
            {
                Name = request.OperatingSystemName,
                Architecture = request.OperatingSystemArchitecture
            },
            RegistrationToken = request.RegistrationToken
        };

        using var cts = CancellationTokenSource.CreateLinkedTokenSource(ct);
        cts.CancelAfter(TimeSpan.FromSeconds(_options.RegistrationTimeoutSeconds));

        HttpResponseMessage response;
        try
        {
            var url = BuildUrl("agents/register");

            // Log sem o token: identificamos a instalação, nunca o segredo.
            _logger.LogInformation(
                "Registrando Agent no Portal (installation_id={InstallationId}, machine_id={MachineId})",
                request.InstallationId, request.MachineId);

            response = await _http.PostAsJsonAsync(url, wire, ProtocolJson.Options, cts.Token);
        }
        catch (OperationCanceledException) when (ct.IsCancellationRequested)
        {
            throw;
        }
        catch (OperationCanceledException)
        {
            _logger.LogWarning("Timeout no registro após {Seconds}s", _options.RegistrationTimeoutSeconds);
            return PortalRegistrationOutcome.Transient(
                RegistrationReasonCodes.Unreachable,
                $"Timeout após {_options.RegistrationTimeoutSeconds}s.");
        }
        catch (HttpRequestException ex)
        {
            _logger.LogWarning(ex, "Portal inacessível durante o registro");
            return PortalRegistrationOutcome.Transient(RegistrationReasonCodes.Unreachable, ex.Message);
        }

        using (response)
        {
            if (response.IsSuccessStatusCode)
                return await ReadSuccessAsync(response, cts.Token);

            return await ReadFailureAsync(response, cts.Token);
        }
    }

    private async Task<PortalRegistrationOutcome> ReadSuccessAsync(HttpResponseMessage response, CancellationToken ct)
    {
        RegistrationResponse? body;
        try
        {
            body = await response.Content.ReadFromJsonAsync<RegistrationResponse>(ProtocolJson.Options, ct);
        }
        catch (JsonException ex)
        {
            _logger.LogError(ex, "Resposta de registro do Portal não pôde ser interpretada");
            return PortalRegistrationOutcome.Rejected(RegistrationReasonCodes.InvalidResponse, ex.Message);
        }

        if (body is null || string.IsNullOrWhiteSpace(body.AgentId))
        {
            return PortalRegistrationOutcome.Rejected(
                RegistrationReasonCodes.InvalidResponse, "Resposta sem agent_id.");
        }

        if (body.Credential is null || string.IsNullOrWhiteSpace(body.Credential.Value))
        {
            return PortalRegistrationOutcome.Rejected(
                RegistrationReasonCodes.InvalidResponse, "Resposta sem credencial.");
        }

        var credential = new AgentCredential
        {
            Type = body.Credential.Type,
            Value = body.Credential.Value,
            ExpiresAtUtc = body.Credential.ExpiresAt?.ToUniversalTime(),
            StoredAtUtc = _clock.UtcNow
        };

        var endpoints = body.Portal is null
            ? null
            : new PortalEndpoints(body.Portal.WebSocketUrl, body.Portal.ApiBaseUrl);

        _logger.LogInformation("Portal atribuiu agent_id={AgentId}", body.AgentId);
        return PortalRegistrationOutcome.Ok(body.AgentId, credential, endpoints);
    }

    private async Task<PortalRegistrationOutcome> ReadFailureAsync(HttpResponseMessage response, CancellationToken ct)
    {
        RegistrationFailure? failure = null;
        try
        {
            failure = await response.Content.ReadFromJsonAsync<RegistrationFailure>(ProtocolJson.Options, ct);
        }
        catch (Exception ex) when (ex is JsonException or NotSupportedException or HttpRequestException)
        {
            // Corpo não estruturado — classificamos pelo status HTTP.
        }

        var reasonCode = failure?.ReasonCode ?? MapStatusToReason(response.StatusCode);
        var message = failure?.Message ?? $"Portal respondeu {(int)response.StatusCode} {response.ReasonPhrase}.";

        // 5xx e 429 são transitórios; 4xx restantes são rejeição definitiva.
        var retryable = failure?.Retryable
                        ?? response.StatusCode is HttpStatusCode.TooManyRequests
                            or HttpStatusCode.RequestTimeout
                        || (int)response.StatusCode >= 500;

        _logger.LogWarning(
            "Registro rejeitado pelo Portal: status={Status}, reason={Reason}, retryable={Retryable}",
            (int)response.StatusCode, reasonCode, retryable);

        return retryable
            ? PortalRegistrationOutcome.Transient(reasonCode, message)
            : PortalRegistrationOutcome.Rejected(reasonCode, message);
    }

    private static string MapStatusToReason(HttpStatusCode status) => status switch
    {
        HttpStatusCode.Unauthorized => RegistrationReasonCodes.InvalidToken,
        HttpStatusCode.Forbidden => RegistrationReasonCodes.Revoked,
        HttpStatusCode.Conflict => RegistrationReasonCodes.TokenAlreadyUsed,
        HttpStatusCode.Gone => RegistrationReasonCodes.TokenExpired,
        HttpStatusCode.UpgradeRequired => RegistrationReasonCodes.VersionUnsupported,
        _ => "REGISTRATION_FAILED"
    };

    private string BuildUrl(string relativePath)
    {
        var baseUrl = _options.ApiBaseUrl.TrimEnd('/');
        return $"{baseUrl}/{relativePath}";
    }
}
