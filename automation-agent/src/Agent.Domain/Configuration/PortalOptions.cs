using System.ComponentModel.DataAnnotations;

namespace Biason.AutomationAgent.Domain.Configuration;

public sealed class PortalOptions : IValidatableObject
{
    public const string Section = "Portal";

    /// <summary>Quando false, o Agent opera apenas localmente e não tenta contatar o Portal.</summary>
    public bool Enabled { get; init; } = true;

    public string ApiBaseUrl { get; init; } = string.Empty;

    public string WebSocketUrl { get; init; } = string.Empty;

    /// <summary>
    /// Token de registro de uso limitado. Preferir variável de ambiente
    /// (AUTOMATION_AGENT_Portal__RegistrationToken) a arquivo em disco.
    /// </summary>
    public string? RegistrationToken { get; init; }

    [Range(5, 300)]
    public int ConnectionTimeoutSeconds { get; init; } = 30;

    [Range(5, 300)]
    public int HeartbeatIntervalSeconds { get; init; } = 15;

    [Range(5, 600)]
    public int ReconnectMaximumSeconds { get; init; } = 120;

    [Range(1, 60)]
    public int ReconnectInitialSeconds { get; init; } = 2;

    [Range(10, 600)]
    public int RegistrationTimeoutSeconds { get; init; } = 60;

    /// <summary>Dias antes da expiração em que a credencial é considerada rotacionável.</summary>
    [Range(1, 90)]
    public int CredentialRotationThresholdDays { get; init; } = 7;

    /// <summary>Exige HTTPS/WSS. Só desative em ambiente de teste local controlado.</summary>
    public bool RequireSecureTransport { get; init; } = true;

    public IEnumerable<ValidationResult> Validate(ValidationContext validationContext)
    {
        if (!Enabled)
            yield break;

        if (string.IsNullOrWhiteSpace(ApiBaseUrl))
        {
            yield return new ValidationResult(
                "Portal.ApiBaseUrl é obrigatório quando Portal.Enabled = true.",
                new[] { nameof(ApiBaseUrl) });
        }
        else if (!Uri.TryCreate(ApiBaseUrl, UriKind.Absolute, out var apiUri))
        {
            yield return new ValidationResult(
                $"Portal.ApiBaseUrl inválido: '{ApiBaseUrl}'.", new[] { nameof(ApiBaseUrl) });
        }
        else if (RequireSecureTransport && apiUri.Scheme != Uri.UriSchemeHttps)
        {
            yield return new ValidationResult(
                "Portal.ApiBaseUrl deve usar HTTPS. Ajuste RequireSecureTransport apenas em teste local.",
                new[] { nameof(ApiBaseUrl) });
        }

        if (string.IsNullOrWhiteSpace(WebSocketUrl))
        {
            yield return new ValidationResult(
                "Portal.WebSocketUrl é obrigatório quando Portal.Enabled = true.",
                new[] { nameof(WebSocketUrl) });
        }
        else if (!Uri.TryCreate(WebSocketUrl, UriKind.Absolute, out var wsUri))
        {
            yield return new ValidationResult(
                $"Portal.WebSocketUrl inválido: '{WebSocketUrl}'.", new[] { nameof(WebSocketUrl) });
        }
        else if (RequireSecureTransport && wsUri.Scheme != "wss")
        {
            yield return new ValidationResult(
                "Portal.WebSocketUrl deve usar WSS. Ajuste RequireSecureTransport apenas em teste local.",
                new[] { nameof(WebSocketUrl) });
        }

        if (HeartbeatIntervalSeconds >= ConnectionTimeoutSeconds)
        {
            yield return new ValidationResult(
                "Portal.HeartbeatIntervalSeconds deve ser menor que ConnectionTimeoutSeconds.",
                new[] { nameof(HeartbeatIntervalSeconds) });
        }

        if (ReconnectInitialSeconds > ReconnectMaximumSeconds)
        {
            yield return new ValidationResult(
                "Portal.ReconnectInitialSeconds não pode exceder ReconnectMaximumSeconds.",
                new[] { nameof(ReconnectInitialSeconds) });
        }
    }
}
