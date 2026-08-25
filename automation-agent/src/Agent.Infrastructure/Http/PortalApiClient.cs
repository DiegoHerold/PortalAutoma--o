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
            LocalIdentity = request.MachineId,
            MachineFingerprint = request.MachineId,
            Name = request.Name,
            Hostname = request.Hostname,
            AgentVersion = request.AgentVersion,
            OperatingSystem = request.OperatingSystemName,
            Architecture = request.OperatingSystemArchitecture,
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

    public async Task<PortalArtifactUploadTargetOutcome> RequestArtifactUploadAsync(
        PortalArtifactUploadRequest request,
        CancellationToken ct = default)
    {
        try
        {
            using var response = await _http.PostAsJsonAsync(
                BuildUrl("artifacts/upload-requests"),
                request,
                ProtocolJson.Options,
                ct);

            if (!response.IsSuccessStatusCode)
                return PortalArtifactUploadTargetOutcome.Failed(
                    MapArtifactStatusToReason(response.StatusCode),
                    $"Portal respondeu {(int)response.StatusCode} {response.ReasonPhrase}.",
                    IsRetryable(response.StatusCode));

            var target = await response.Content.ReadFromJsonAsync<PortalArtifactUploadTarget>(ProtocolJson.Options, ct);
            return target is null || string.IsNullOrWhiteSpace(target.UploadUrl)
                ? PortalArtifactUploadTargetOutcome.Failed("ARTIFACT_UPLOAD_TARGET_INVALID", "Resposta sem upload_url.", retryable: true)
                : PortalArtifactUploadTargetOutcome.Ok(target);
        }
        catch (OperationCanceledException) when (ct.IsCancellationRequested)
        {
            throw;
        }
        catch (Exception ex) when (ex is HttpRequestException or JsonException or NotSupportedException)
        {
            _logger.LogWarning(ex, "Falha ao solicitar upload de artefato {ArtifactId}", request.ArtifactId);
            return PortalArtifactUploadTargetOutcome.Failed("ARTIFACT_UPLOAD_REQUEST_FAILED", ex.Message, retryable: true);
        }
    }

    public async Task<PortalArtifactUploadOutcome> UploadArtifactContentAsync(
        PortalArtifactUploadTarget target,
        string localPath,
        string contentType,
        CancellationToken ct = default)
    {
        try
        {
            var url = Uri.TryCreate(target.UploadUrl, UriKind.Absolute, out _)
                ? target.UploadUrl
                : BuildUrl(target.UploadUrl.TrimStart('/'));

            await using var stream = File.OpenRead(localPath);
            using var content = new StreamContent(stream);
            content.Headers.ContentType = new System.Net.Http.Headers.MediaTypeHeaderValue(contentType);

            using var request = new HttpRequestMessage(new HttpMethod(target.Method), url)
            {
                Content = content
            };

            using var response = await _http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, ct);
            return response.IsSuccessStatusCode
                ? PortalArtifactUploadOutcome.Ok()
                : PortalArtifactUploadOutcome.Failed(
                    MapArtifactStatusToReason(response.StatusCode),
                    $"Upload respondeu {(int)response.StatusCode} {response.ReasonPhrase}.",
                    IsRetryable(response.StatusCode));
        }
        catch (OperationCanceledException) when (ct.IsCancellationRequested)
        {
            throw;
        }
        catch (Exception ex) when (ex is IOException or HttpRequestException)
        {
            _logger.LogWarning(ex, "Falha ao enviar artefato em {Path}", localPath);
            return PortalArtifactUploadOutcome.Failed("ARTIFACT_UPLOAD_FAILED", ex.Message, retryable: true);
        }
    }

    public async Task<PortalArtifactUploadOutcome> ConfirmArtifactUploadAsync(
        PortalArtifactUploadConfirmation confirmation,
        CancellationToken ct = default)
    {
        try
        {
            using var response = await _http.PostAsJsonAsync(
                BuildUrl($"artifacts/{Uri.EscapeDataString(confirmation.ArtifactId)}/confirm"),
                confirmation,
                ProtocolJson.Options,
                ct);

            return response.IsSuccessStatusCode
                ? PortalArtifactUploadOutcome.Ok()
                : PortalArtifactUploadOutcome.Failed(
                    MapArtifactStatusToReason(response.StatusCode),
                    $"Confirmação respondeu {(int)response.StatusCode} {response.ReasonPhrase}.",
                    IsRetryable(response.StatusCode));
        }
        catch (OperationCanceledException) when (ct.IsCancellationRequested)
        {
            throw;
        }
        catch (Exception ex) when (ex is HttpRequestException or JsonException or NotSupportedException)
        {
            _logger.LogWarning(ex, "Falha ao confirmar artefato {ArtifactId}", confirmation.ArtifactId);
            return PortalArtifactUploadOutcome.Failed("ARTIFACT_CONFIRMATION_FAILED", ex.Message, retryable: true);
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

        var agentId = body?.AgentId ?? body?.Agent?.Id;
        if (body is null || string.IsNullOrWhiteSpace(agentId))
        {
            return PortalRegistrationOutcome.Rejected(
                RegistrationReasonCodes.InvalidResponse, "Resposta sem agent_id.");
        }

        var credentialValue = ResolveCredentialValue(body.Credential);
        if (body.Credential is null || string.IsNullOrWhiteSpace(credentialValue))
        {
            return PortalRegistrationOutcome.Rejected(
                RegistrationReasonCodes.InvalidResponse, "Resposta sem credencial.");
        }

        var credential = new AgentCredential
        {
            Type = string.IsNullOrWhiteSpace(body.Credential.Type) ? "client_token" : body.Credential.Type,
            Value = credentialValue,
            ExpiresAtUtc = body.Credential.ExpiresAt?.ToUniversalTime(),
            StoredAtUtc = _clock.UtcNow
        };

        var endpoints = body.Portal is null
            ? null
            : new PortalEndpoints(body.Portal.WebSocketUrl, body.Portal.ApiBaseUrl);

        _logger.LogInformation("Portal atribuiu agent_id={AgentId}", agentId);
        return PortalRegistrationOutcome.Ok(agentId, credential, endpoints);
    }

    private static string? ResolveCredentialValue(RegistrationCredential? credential)
    {
        if (credential is null)
            return null;

        if (!string.IsNullOrWhiteSpace(credential.Value))
            return credential.Value;

        if (!string.IsNullOrWhiteSpace(credential.BearerToken))
            return credential.BearerToken;

        if (!string.IsNullOrWhiteSpace(credential.PublicIdentifier) &&
            !string.IsNullOrWhiteSpace(credential.Secret))
            return $"{credential.PublicIdentifier}:{credential.Secret}";

        return null;
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

    private static string MapArtifactStatusToReason(HttpStatusCode status) => status switch
    {
        HttpStatusCode.NotFound => "ARTIFACT_UPLOAD_TARGET_NOT_FOUND",
        HttpStatusCode.Unauthorized or HttpStatusCode.Forbidden => "ARTIFACT_UPLOAD_UNAUTHORIZED",
        HttpStatusCode.RequestEntityTooLarge => "ARTIFACT_TOO_LARGE",
        HttpStatusCode.Conflict => "ARTIFACT_UPLOAD_CONFLICT",
        _ => "ARTIFACT_UPLOAD_HTTP_ERROR"
    };

    private static bool IsRetryable(HttpStatusCode status) =>
        status is HttpStatusCode.TooManyRequests or HttpStatusCode.RequestTimeout ||
        (int)status >= 500;

    private string BuildUrl(string relativePath)
    {
        var baseUrl = _options.ApiBaseUrl.TrimEnd('/');
        return $"{baseUrl}/{relativePath}";
    }
}
